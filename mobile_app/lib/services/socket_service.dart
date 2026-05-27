import 'dart:convert';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:socket_io_client/socket_io_client.dart' as socket_io;
import 'package:uuid/uuid.dart';

import '../config/app_config.dart';
import '../models/chat_session.dart';
import '../utils/server_url.dart';
import '../models/memory_fact.dart';
import '../models/message.dart';

class SocketService with ChangeNotifier {
  static const _uuid = Uuid();

  socket_io.Socket? _socket;
  final AudioPlayer _audioPlayer = AudioPlayer();

  int _connectionGen = 0;
  bool _connectPending = false;
  String? _activeConnectUrl;
  String _serverUrl = AppConfig.emulatorHostUrl;
  String? _sessionId;
  String _mode = 'pirandello';
  bool _isStreaming = false;
  bool _autoplay = false;
  bool _ttsInFlight = false;
  bool _gateResponse = false;
  String? _lastConnectionError;
  String _activeProvider = AppConfig.defaultProvider;
  Map<String, Map<String, dynamic>> _providers = {};

  final List<ChatMessage> _messages = [];
  List<ChatSession> _sessions = [];
  List<MemoryFact> _memories = [];

  bool get isConnected => _socket?.connected == true;
  bool get isStreaming => _isStreaming;
  bool get autoplay => _autoplay;
  String get activeProvider => _activeProvider;
  Map<String, Map<String, dynamic>> get providers => _providers;
  List<ChatMessage> get messages => List.unmodifiable(_messages);
  List<ChatSession> get sessions => List.unmodifiable(_sessions);
  List<MemoryFact> get memories => List.unmodifiable(_memories);
  String? get sessionId => _sessionId;
  String get mode => _mode;
  String get serverUrl => _serverUrl;
  String? get lastConnectionError => _lastConnectionError;
  bool get hasActiveChat => _sessionId != null && _messages.isNotEmpty;

  SocketService() {
    _init();
  }

  Future<void> _init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(AppConfig.prefsServerUrl);
    _serverUrl = normalizeServerUrl(saved ?? AppConfig.emulatorHostUrl);
    _mode = prefs.getString(AppConfig.prefsLastMode) ?? 'pirandello';
    _autoplay = prefs.getBool(AppConfig.prefsAutoplay) ?? false;
    _activeProvider = prefs.getString(AppConfig.prefsActiveProvider) ?? AppConfig.defaultProvider;
    connect();
  }

  String get apiBase => _serverUrl.replaceAll(RegExp(r'/$'), '');

  Future<void> setMode(String mode) async {
    if (_mode == mode) return;
    _mode = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.prefsLastMode, mode);
    _sessionId = null;
    _messages.clear();
    await _audioPlayer.stop();
    notifyListeners();
    await fetchSessions();
  }

  Future<void> setAutoplay(bool value) async {
    _autoplay = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(AppConfig.prefsAutoplay, value);
    notifyListeners();
  }

  Future<void> updateServerUrl(String url) async {
    _serverUrl = normalizeServerUrl(url);
    _lastConnectionError = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.prefsServerUrl, _serverUrl);
    _sessionId = null;
    _messages.clear();
    connect(force: true);
    await fetchSessions();
  }

  /// Ricrea il socket solo se cambia URL o [force] è true.
  void connect({bool force = false}) {
    if (!force &&
        _activeConnectUrl == apiBase &&
        _socket != null &&
        (_socket!.connected || _connectPending)) {
      return;
    }

    _connectionGen++;
    final gen = _connectionGen;
    _activeConnectUrl = apiBase;
    _connectPending = true;

    final previous = _socket;
    if (previous != null) {
      previous.clearListeners();
      previous.disconnect();
    }

    // Su Android/iOS (dart:io) socket_io_client supporta SOLO WebSocket nativo
    // (io_transports.dart). "polling" apre comunque un WS con ?transport=polling
    // e il server chiude subito — usare esplicitamente websocket.
    final socket = socket_io.io(
      apiBase,
      socket_io.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .enableReconnection()
          .setReconnectionAttempts(30)
          .setReconnectionDelay(1000)
          .setReconnectionDelayMax(5000)
          .setTimeout(20000)
          .build(),
    );
    _socket = socket;
    _lastConnectionError = null;

    bool isCurrent() => identical(_socket, socket) && _connectionGen == gen;

    socket.onConnect((_) {
      if (!isCurrent()) return;
      _connectPending = false;
      _lastConnectionError = null;
      debugPrint('Socket connected → $apiBase');
      fetchSessions();
      notifyListeners();
    });

    socket.onDisconnect((reason) {
      if (!isCurrent()) return;
      _connectPending = false;
      _lastConnectionError = reason?.toString() ?? 'disconnect';
      debugPrint('Socket disconnected: $_lastConnectionError');
      if (_isStreaming) {
        _isStreaming = false;
        _finishAssistantMessage();
      }
      notifyListeners();
    });

    socket.onConnectError((data) {
      if (!isCurrent()) return;
      _connectPending = false;
      _lastConnectionError = data?.toString() ?? 'connect_error';
      debugPrint('Socket connect_error: $_lastConnectionError');
      notifyListeners();
    });

    socket.onError((data) {
      if (!isCurrent()) return;
      _lastConnectionError = data?.toString() ?? 'socket_error';
      debugPrint('Socket error: $_lastConnectionError');
      notifyListeners();
    });

    // session_ready ignorato (home senza chat automatica)

    socket.on('assistant_preparing', (data) {
      if (!isCurrent()) return;
      final sid = data['session_id'] as String?;
      if (sid != null && _sessionId != null && sid != _sessionId) return;
      _messages.add(ChatMessage(
        id: _uuid.v4(),
        text: '',
        sender: MessageSender.assistant,
        timestamp: DateTime.now(),
        isStreaming: true,
        isPreparing: true,
      ));
      _isStreaming = true;
      notifyListeners();
    });

    socket.on('assistant_ready', (data) {
      if (!isCurrent()) return;
      final sid = data['session_id'] as String?;
      if (sid != null && _sessionId != null && sid != _sessionId) return;
      _gateResponse = false;
      _isStreaming = false;
      _ttsInFlight = false;
      final text = data['text']?.toString() ?? '';
      final url = data['audio_url']?.toString();
      final ttsError = data['tts_error']?.toString();

      final prepIdx = _messages.lastIndexWhere(
        (m) => m.sender == MessageSender.assistant && m.isPreparing,
      );
      final msg = ChatMessage(
        id: prepIdx >= 0 ? _messages[prepIdx].id : _uuid.v4(),
        text: text,
        sender: MessageSender.assistant,
        timestamp: DateTime.now(),
        isStreaming: false,
        isPreparing: false,
        audioUrl: url,
      );
      if (prepIdx >= 0) {
        _messages[prepIdx] = msg;
      } else {
        _messages.add(msg);
      }
      notifyListeners();

      if (ttsError != null && ttsError.isNotEmpty) {
        debugPrint('TTS error: $ttsError');
      }
      if (url != null && url.isNotEmpty && _autoplay) {
        playAudioUrl(url);
      }
    });

    socket.on('token', (data) {
      if (!isCurrent()) return;
      if (_gateResponse) return;
      final sid = data['session_id'] as String?;
      if (sid != null && _sessionId != null && sid != _sessionId) return;
      final token = data['token']?.toString() ?? '';
      _appendAssistantToken(token);
    });

    socket.on('done', (data) {
      if (!isCurrent()) return;
      final sid = data['session_id'] as String?;
      if (sid != null && _sessionId != null && sid != _sessionId) return;
      final gated = data is Map && data['gated'] == true;
      if (gated) {
        _isStreaming = false;
        fetchSessions();
        return;
      }
      _finishAssistantMessage();
      fetchSessions();
    });

    socket.on('session_created', (_) {
      if (isCurrent()) fetchSessions();
    });
    socket.on('session_updated', (data) {
      if (!isCurrent()) return;
      final id = data['id'] as String?;
      final title = data['title'] as String?;
      if (id == null || title == null) return;
      final idx = _sessions.indexWhere((s) => s.id == id);
      if (idx >= 0) {
        final old = _sessions[idx];
        _sessions[idx] = ChatSession(
          id: old.id,
          title: title,
          createdAt: old.createdAt,
          mode: old.mode,
        );
        notifyListeners();
      } else {
        fetchSessions();
      }
    });
    socket.on('session_deleted', (data) {
      if (!isCurrent()) return;
      final id = data['session_id'] as String?;
      if (id == _sessionId) {
        _sessionId = null;
        _messages.clear();
      }
      fetchSessions();
    });
    socket.on('all_data_cleared', (data) {
      if (!isCurrent()) return;
      if (data is Map && data['hard_reset'] == true) {
        _sessionId = null;
        _messages.clear();
        _sessions.clear();
        _memories.clear();
        notifyListeners();
      }
    });

    socket.on('tts_ready', (data) {
      if (!isCurrent()) return;
      _ttsInFlight = false;
      final url = data['url']?.toString() ?? data['path']?.toString();
      if (url == null || url.isEmpty) return;
      _setLastAssistantAudioUrl(url);
      playAudioUrl(url);
    });

    socket.on('tts_error', (data) {
      if (!isCurrent()) return;
      _ttsInFlight = false;
      debugPrint('TTS error: ${data['error']}');
      notifyListeners();
    });

    socket.on('memory_updated', (_) {
      if (isCurrent()) fetchMemories();
    });

    socket.on('upload_result', (data) {
      if (!isCurrent()) return;
      if (data['success'] == true) {
        _messages.add(ChatMessage(
          id: _uuid.v4(),
          text: 'Documento aggiunto: ${data['filename']}',
          sender: MessageSender.system,
          timestamp: DateTime.now(),
        ));
        notifyListeners();
      }
    });

    socket.connect();
  }

  Future<bool> _ensureConnected({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    if (_socket?.connected == true) return true;

    if (_socket == null || _activeConnectUrl != apiBase) {
      connect(force: _activeConnectUrl != apiBase);
    } else if (!_connectPending && _socket?.connected != true) {
      _connectPending = true;
      _socket!.connect();
    }

    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      if (_socket?.connected == true) return true;
      await Future.delayed(const Duration(milliseconds: 150));
    }
    _connectPending = false;
    return _socket?.connected == true;
  }

  void _appendAssistantToken(String token) {
    if (_messages.isNotEmpty &&
        _messages.last.sender == MessageSender.assistant &&
        _messages.last.isStreaming) {
      final last = _messages.last;
      _messages[_messages.length - 1] =
          last.copyWith(text: last.text + token);
    } else {
      _messages.add(ChatMessage(
        id: _uuid.v4(),
        text: token,
        sender: MessageSender.assistant,
        timestamp: DateTime.now(),
        isStreaming: true,
      ));
    }
    _isStreaming = true;
    notifyListeners();
  }

  void _finishAssistantMessage() {
    _isStreaming = false;
    if (_messages.isNotEmpty &&
        _messages.last.sender == MessageSender.assistant) {
      final last = _messages.last;
      _messages[_messages.length - 1] = last.copyWith(isStreaming: false);
    }
    notifyListeners();
  }

  void _setLastAssistantAudioUrl(String url) {
    for (var i = _messages.length - 1; i >= 0; i--) {
      if (_messages[i].sender == MessageSender.assistant) {
        _messages[i] = _messages[i].copyWith(audioUrl: url);
        break;
      }
    }
    notifyListeners();
  }

  Future<void> fetchSessions({String? query}) async {
    try {
      final q = (query ?? '').trim();
      var uri = '$apiBase/api/sessions?mode=${Uri.encodeQueryComponent(_mode)}';
      if (q.isNotEmpty) {
        uri += '&q=${Uri.encodeQueryComponent(q)}';
      }
      final res = await http.get(Uri.parse(uri));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final list = data['sessions'] as List<dynamic>? ?? [];
        _sessions = list
            .map((e) => ChatSession.fromJson(e as Map<String, dynamic>))
            .toList();
        notifyListeners();
      }
    } catch (e) {
      debugPrint('fetchSessions: $e');
    }
  }

  Future<void> fetchMemories() async {
    try {
      final res = await http.get(Uri.parse('$apiBase/api/memories'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final list = data['memories'] as List<dynamic>? ?? [];
        _memories = list
            .map((e) => MemoryFact.fromJson(e as Map<String, dynamic>))
            .toList();
        notifyListeners();
      }
    } catch (e) {
      debugPrint('fetchMemories: $e');
    }
  }

  Future<void> fetchProviders() async {
    try {
      final res = await http.get(Uri.parse('$apiBase/api/providers'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        _providers = (data['providers'] as Map<String, dynamic>?)
                ?.map((k, v) => MapEntry(k, v as Map<String, dynamic>)) ??
            {};
        _activeProvider = data['active'] as String? ?? AppConfig.defaultProvider;
        notifyListeners();
      }
    } catch (e) {
      debugPrint('fetchProviders: $e');
    }
  }

  Future<void> activateProvider(String name) async {
    if (name == _activeProvider) return;
    try {
      await http.post(
        Uri.parse('$apiBase/api/providers/activate?name=${Uri.encodeQueryComponent(name)}'),
      );
      _activeProvider = name;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConfig.prefsActiveProvider, name);
      notifyListeners();
    } catch (e) {
      debugPrint('activateProvider: $e');
    }
  }

  Future<void> updateProviderConfig(String name, Map<String, dynamic> config) async {
    try {
      await http.post(
        Uri.parse('$apiBase/api/providers/config?name=${Uri.encodeQueryComponent(name)}'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(config),
      );
      await fetchProviders();
    } catch (e) {
      debugPrint('updateProviderConfig: $e');
    }
  }

  Future<void> loadSession(String id) async {
    try {
      final res = await http.get(Uri.parse('$apiBase/api/sessions/$id/messages'));
      if (res.statusCode != 200) return;
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      _sessionId = id;
      _messages.clear();
      for (final m in data['messages'] as List<dynamic>? ?? []) {
        final role = m['role'] as String? ?? 'user';
        _messages.add(ChatMessage(
          id: _uuid.v4(),
          text: m['content'] as String? ?? '',
          sender: role == 'user'
              ? MessageSender.user
              : role == 'system'
                  ? MessageSender.system
                  : MessageSender.assistant,
          timestamp: DateTime.now(),
        ));
      }
      notifyListeners();
    } catch (e) {
      debugPrint('loadSession: $e');
    }
  }

  void newChat() {
    _sessionId = null;
    _messages.clear();
    notifyListeners();
  }

  Future<void> deleteSession(String id) async {
    _sessions.removeWhere((s) => s.id == id);
    if (_sessionId == id) {
      _sessionId = null;
      _messages.clear();
    }
    notifyListeners();
    try {
      await http.delete(Uri.parse('$apiBase/api/sessions/${Uri.encodeComponent(id)}'));
    } catch (e) {
      debugPrint('deleteSession HTTP: $e');
      await fetchSessions();
    }
    if (_socket?.connected == true) {
      _socket!.emit('delete_session', {'session_id': id});
    }
  }

  Future<void> hardReset() async {
    _sessionId = null;
    _messages.clear();
    _sessions.clear();
    _memories.clear();
    notifyListeners();
    try {
      await http.delete(Uri.parse('$apiBase/api/sessions?hard_reset=true'));
    } catch (e) {
      debugPrint('hardReset HTTP: $e');
    }
    if (_socket?.connected == true) {
      _socket!.emit('clear_all_data', {'hard_reset': true});
    }
  }

  Future<void> deleteMemory(String category, String key) async {
    try {
      await http.delete(
        Uri.parse(
          '$apiBase/api/memories?category=${Uri.encodeQueryComponent(category)}&key=${Uri.encodeQueryComponent(key)}',
        ),
      );
      await fetchMemories();
    } catch (e) {
      debugPrint('deleteMemory: $e');
    }
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty || _isStreaming) return;

    if (!await _ensureConnected()) {
      _lastConnectionError = 'Socket non connesso';
      notifyListeners();
      return;
    }

    if (_sessionId == null) {
      _sessionId = _uuid.v4();
      _socket!.emit('create_session', {
        'session_id': _sessionId,
        'title': text,
        'mode': _mode,
      });
    }

    _messages.add(ChatMessage(
      id: _uuid.v4(),
      text: text,
      sender: MessageSender.user,
      timestamp: DateTime.now(),
    ));
    _isStreaming = true;
    _gateResponse = _mode == 'pirandello' && _autoplay;
    notifyListeners();

    _socket!.emit('chat_message', {
      'message': text,
      'session_id': _sessionId,
      'mode': _mode,
      'history': [],
      'autovoice': _mode == 'pirandello' && _autoplay,
      'provider': _activeProvider,
    });
  }

  void requestTts(String message, {String? cachedUrl}) {
    if (cachedUrl != null && cachedUrl.isNotEmpty) {
      playAudioUrl(cachedUrl);
      return;
    }
    if (_ttsInFlight || _sessionId == null) return;
    _ttsInFlight = true;
    _socket?.emit('request_tts', {
      'message': message,
      'session_id': _sessionId,
    });
  }

  Future<void> playAudioUrl(String pathOrUrl) async {
    final base = pathOrUrl.startsWith('http') ? pathOrUrl : '$apiBase$pathOrUrl';
    final sep = base.contains('?') ? '&' : '?';
    final src = '$base${sep}t=${DateTime.now().millisecondsSinceEpoch}';
    try {
      await _audioPlayer.stop();
      await _audioPlayer.play(UrlSource(src));
    } catch (e) {
      debugPrint('playAudioUrl: $e');
    }
  }

  Future<void> stopAudio() async {
    await _audioPlayer.stop();
  }

  Future<String?> uploadFile(File file) async {
    if (!await _ensureConnected()) {
      _lastConnectionError = 'Socket non connesso';
      notifyListeners();
      return null;
    }
    try {
      final bytes = await file.readAsBytes();
      final base64str = base64.encode(bytes);
      _socket!.emit('upload_file', {
        'filename': file.path.split(Platform.pathSeparator).last,
        'file': base64str,
      });
      return file.path;
    } catch (e) {
      debugPrint('Upload error: $e');
      return null;
    }
  }

  /// Testa HTTP e Socket verso [url] (normalizzato). Non salva le preferenze.
  Future<ConnectionTestResult> testConnection([String? url]) async {
    final base = normalizeServerUrl(url ?? _serverUrl);
    String? httpError;
    bool httpOk = false;

    try {
      final res = await http
          .get(Uri.parse('$base/health'))
          .timeout(const Duration(seconds: 8));
      httpOk = res.statusCode == 200;
      if (!httpOk) httpError = 'HTTP ${res.statusCode}';
    } catch (e) {
      httpError = e.toString();
    }

    bool socketOk = _socket?.connected == true && apiBase == base;
    if (httpOk && !socketOk) {
      if (apiBase != base) {
        await updateServerUrl(base);
      }
      socketOk = await _ensureConnected(timeout: const Duration(seconds: 8));
    }

    return ConnectionTestResult(
      normalizedUrl: base,
      httpOk: httpOk,
      socketOk: socketOk,
      httpError: httpError,
      socketError: socketOk ? null : _lastConnectionError,
    );
  }

  Future<bool> checkHealth() async {
    final r = await testConnection();
    return r.httpOk;
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    _socket?.disconnect();
    super.dispose();
  }
}

class ConnectionTestResult {
  final String normalizedUrl;
  final bool httpOk;
  final bool socketOk;
  final String? httpError;
  final String? socketError;

  ConnectionTestResult({
    required this.normalizedUrl,
    required this.httpOk,
    required this.socketOk,
    this.httpError,
    this.socketError,
  });

  bool get ok => httpOk && socketOk;

  String get message {
    if (ok) return 'Connesso a $normalizedUrl';
    if (!httpOk) {
      return 'HTTP fallito su $normalizedUrl\n'
          '${httpError ?? "verifica IP Tailscale e :8000"}';
    }
    return 'HTTP ok, Socket no su $normalizedUrl\n'
        '${socketError ?? "riprova Applica"}';
  }
}
