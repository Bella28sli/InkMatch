import 'app_config.dart';

const String _cloudinaryPrefix = 'cloudinary:';
const String _localPrefix = 'local:';
const String _yandexPrefix = 'yandex:';

/// Helper to resolve media URLs from different storage backends
class MediaUrlHelper {
  static String? resolveUrl(String? reference) {
    if (reference == null || reference.isEmpty) {
      return null;
    }

    // Handle Cloudinary references (these are already signed URLs or public IDs)
    if (reference.startsWith(_cloudinaryPrefix)) {
      // If the API returns cloudinary: prefix, it means it's the public ID
      // The server will handle generating signed URLs, so we can pass it as-is
      // Or we can construct the Cloudinary URL here if needed
      return reference;
    }

    // Handle local storage references (local:kind/owner_id/filename)
    if (reference.startsWith(_localPrefix)) {
      final relativePath = reference.substring(_localPrefix.length);
      final baseUrl = AppConfig.apiBaseUrl;
      return '$baseUrl/uploads/$relativePath';
    }

    if (reference.startsWith(_yandexPrefix)) {
      final key = reference.substring(_yandexPrefix.length);
      return 'https://inkmatch.storage.yandexcloud.net/$key';
    }

    // If it's already a full URL (starts with http/https), return as-is
    if (reference.startsWith('http://') || reference.startsWith('https://')) {
      return reference;
    }

    // Otherwise return the reference as-is (might be a path or unrecognized format)
    return reference;
  }

  /// Check if a reference is from local storage
  static bool isLocal(String? reference) {
    return reference != null && reference.startsWith(_localPrefix);
  }

  /// Check if a reference is from Cloudinary
  static bool isCloudinary(String? reference) {
    return reference != null && reference.startsWith(_cloudinaryPrefix);
  }

  static bool isYandex(String? reference) {
    return reference != null && reference.startsWith(_yandexPrefix);
  }
}
