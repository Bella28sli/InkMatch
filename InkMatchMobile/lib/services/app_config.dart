import 'package:flutter/services.dart';

class AppConfig {
  AppConfig._();

  static const _definedApiBaseUrl = String.fromEnvironment(
    'INKMATCH_API_BASE_URL',
  );

  static const _channel = MethodChannel('inkmatch/config');

  static String _apiBaseUrl = _definedApiBaseUrl;

  static String get apiBaseUrl {
    if (_apiBaseUrl.isNotEmpty) {
      return _apiBaseUrl;
    }
    return 'http://10.0.2.2:8000/api/v1';
  }

  static Future<void> init() async {
    if (_apiBaseUrl.isNotEmpty) return;
    try {
      final fromPlatform = await _channel.invokeMethod<String>('getApiBaseUrl');
      if (fromPlatform != null && fromPlatform.trim().isNotEmpty) {
        _apiBaseUrl = fromPlatform.trim();
      }
    } catch (_) {}
  }
}
