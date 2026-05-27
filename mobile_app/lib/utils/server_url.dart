import '../config/app_config.dart';

/// Normalizza l'URL del backend (sempre con porta 8000 se assente).
String normalizeServerUrl(String input) {
  var raw = input.trim();
  if (raw.isEmpty) return AppConfig.emulatorHostUrl;

  if (!raw.contains('://')) {
    raw = 'http://$raw';
  }

  Uri uri;
  try {
    uri = Uri.parse(raw);
  } catch (_) {
    return AppConfig.emulatorHostUrl;
  }

  if (uri.host.isEmpty) return AppConfig.emulatorHostUrl;

  final scheme = uri.scheme == 'https' ? 'https' : 'http';
  final port = uri.hasPort && uri.port > 0 ? uri.port : 8000;

  return '$scheme://${uri.host}:$port';
}
