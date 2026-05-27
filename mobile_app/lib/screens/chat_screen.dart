import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../services/socket_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_container.dart';
import '../widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  final VoidCallback onOpenHistory;
  final VoidCallback onOpenSettings;

  const ChatScreen({
    super.key,
    required this.onOpenHistory,
    required this.onOpenSettings,
  });

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _audioRecorder = AudioRecorder();
  bool _isRecording = false;

  SocketService? _svc;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final next = context.read<SocketService>();
    if (_svc != next) {
      _svc?.removeListener(_scrollDown);
      _svc = next;
      _svc!.addListener(_scrollDown);
    }
  }

  @override
  void dispose() {
    _svc?.removeListener(_scrollDown);
    _controller.dispose();
    _scrollController.dispose();
    _audioRecorder.dispose();
    super.dispose();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _startRecording() async {
    final status = await Permission.microphone.request();
    if (!status.isGranted) return;
    await _audioRecorder.start(
      const RecordConfig(),
      path: '${DateTime.now().millisecondsSinceEpoch}.m4a',
    );
    setState(() => _isRecording = true);
  }

  Future<void> _stopRecording(SocketService svc) async {
    final path = await _audioRecorder.stop();
    setState(() => _isRecording = false);
    if (path != null) {
      svc.uploadFile(File(path));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SocketService>(
      builder: (context, svc, _) {
        final useMarkdown = svc.mode == 'wiki';

        return Scaffold(
          body: Column(
            children: [
              Container(
                padding: EdgeInsets.only(
                  top: MediaQuery.of(context).padding.top + 8,
                  left: 8,
                  right: 8,
                  bottom: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTheme.bgDark,
                  border: Border(
                    bottom: BorderSide(
                      color: Colors.white.withValues(alpha: 0.05),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Image.asset(
                      'assets/icona.png',
                      width: 28,
                      height: 28,
                    ),
                    const SizedBox(width: 6),
                    IconButton(
                      icon: const Icon(Icons.history, color: Colors.white54),
                      onPressed: widget.onOpenHistory,
                      tooltip: 'Cronologia',
                    ),
                    Expanded(
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.03),
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.06),
                          ),
                        ),
                        padding: const EdgeInsets.all(4),
                        child: Row(
                          children: [
                            Expanded(
                              child: GestureDetector(
                                onTap: () => svc.setMode('pirandello'),
                                child: Container(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 8),
                                  decoration: BoxDecoration(
                                    color: svc.mode == 'pirandello'
                                        ? AppTheme.amberAccent
                                            .withValues(alpha: 0.3)
                                        : Colors.transparent,
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(
                                        Icons.chat_bubble_outline,
                                        size: 16,
                                        color: svc.mode == 'pirandello'
                                            ? Colors.amber.shade100
                                            : Colors.white38,
                                      ),
                                      const SizedBox(width: 6),
                                      Text(
                                        'Pirandello',
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600,
                                          color: svc.mode == 'pirandello'
                                              ? Colors.amber.shade100
                                              : Colors.white38,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                            Expanded(
                              child: GestureDetector(
                                onTap: () => svc.setMode('wiki'),
                                child: Container(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 8),
                                  decoration: BoxDecoration(
                                    color: svc.mode == 'wiki'
                                        ? AppTheme.emeraldAccent
                                            .withValues(alpha: 0.3)
                                        : Colors.transparent,
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(
                                        Icons.menu_book_outlined,
                                        size: 16,
                                        color: svc.mode == 'wiki'
                                            ? Colors.teal.shade100
                                            : Colors.white38,
                                      ),
                                      const SizedBox(width: 6),
                                      Text(
                                        'Wiki',
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600,
                                          color: svc.mode == 'wiki'
                                              ? Colors.teal.shade100
                                              : Colors.white38,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.add, color: Colors.white54),
                      onPressed: svc.newChat,
                      tooltip: 'Nuova chat',
                    ),
                    IconButton(
                      icon: const Icon(Icons.settings, color: Colors.white54),
                      onPressed: widget.onOpenSettings,
                      tooltip: 'Impostazioni',
                    ),
                  ],
                ),
              ),
              if (!svc.isConnected)
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  color: Colors.red.withValues(alpha: 0.15),
                  child: Text(
                    svc.lastConnectionError != null
                        ? 'Non connesso: ${svc.lastConnectionError}\n${svc.serverUrl}'
                        : 'Non connesso — Impostazioni → ${svc.serverUrl}',
                    style: const TextStyle(fontSize: 11, color: Colors.white70),
                    textAlign: TextAlign.center,
                  ),
                ),
              Expanded(
                child: svc.messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.auto_stories,
                              size: 64,
                              color: Colors.white.withValues(alpha: 0.1),
                            ),
                            const SizedBox(height: 16),
                            Text(
                              svc.mode == 'pirandello'
                                  ? '"Parlami di me..."'
                                  : 'Gestione Wiki',
                              style: GoogleFonts.playfairDisplay(
                                fontSize: 22,
                                fontStyle: FontStyle.italic,
                                color: Colors.white.withValues(alpha: 0.3),
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: svc.messages.length,
                        itemBuilder: (context, i) {
                          final msg = svc.messages[i];
                          return MessageBubble(
                            message: msg,
                            useMarkdown: useMarkdown,
                            showTtsButton: svc.mode == 'pirandello',
                            onPlayTts: () => svc.requestTts(
                              msg.text,
                              cachedUrl: msg.audioUrl,
                            ),
                          );
                        },
                      ),
              ),
              Container(
                padding: EdgeInsets.only(
                  left: 12,
                  right: 12,
                  top: 8,
                  bottom: MediaQuery.of(context).padding.bottom + 8,
                ),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      AppTheme.bgDark.withValues(alpha: 0),
                      AppTheme.bgDark,
                    ],
                  ),
                ),
                child: GlassContainer(
                  borderRadius: 24,
                  opacity: 0.06,
                  child: Row(
                    children: [
                      IconButton(
                        icon: Icon(
                          Icons.attach_file,
                          color: Colors.white.withValues(alpha: 0.3),
                          size: 22,
                        ),
                        tooltip: svc.mode == 'wiki'
                            ? 'Carica documento wiki'
                            : 'Carica testo (raw/articles)',
                        onPressed: () async {
                          final result = await FilePicker.platform.pickFiles(
                            type: FileType.any,
                          );
                          if (result != null &&
                              result.files.single.path != null) {
                            await svc.uploadFile(
                              File(result.files.single.path!),
                            );
                          }
                        },
                      ),
                      Expanded(
                        child: TextField(
                          controller: _controller,
                          decoration: InputDecoration(
                            hintText: svc.mode == 'pirandello'
                                ? 'Chiedi a Pirandello...'
                                : 'Comando per il wiki...',
                            hintStyle: TextStyle(
                              color: Colors.white.withValues(alpha: 0.15),
                              fontSize: 14,
                            ),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 12,
                            ),
                          ),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                          ),
                          maxLines: 3,
                          minLines: 1,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (v) async {
                            if (v.trim().isNotEmpty && !svc.isStreaming) {
                              await svc.sendMessage(v);
                              _controller.clear();
                              _scrollDown();
                            }
                          },
                        ),
                      ),
                      IconButton(
                        icon: Icon(
                          _isRecording ? Icons.mic_off : Icons.mic,
                          color: _isRecording
                              ? Colors.red
                              : Colors.white.withValues(alpha: 0.3),
                          size: 22,
                        ),
                        onPressed: () {
                          if (_isRecording) {
                            _stopRecording(svc);
                          } else {
                            _startRecording();
                          }
                        },
                      ),
                      IconButton(
                        icon: Icon(
                          Icons.arrow_upward,
                          color: Colors.white.withValues(
                            alpha: svc.isStreaming ? 0.1 : 0.4,
                          ),
                          size: 22,
                        ),
                        onPressed: svc.isStreaming
                            ? null
                            : () async {
                                final text = _controller.text;
                                if (text.trim().isNotEmpty) {
                                  await svc.sendMessage(text);
                                  _controller.clear();
                                  _scrollDown();
                                }
                              },
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
