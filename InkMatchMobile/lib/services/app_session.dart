import 'package:shared_preferences/shared_preferences.dart';

class AppSession {
  AppSession._();

  static final AppSession instance = AppSession._();

  static const _tokenKey = 'auth_access_token';
  static const _roleKey = 'auth_user_role';

  String? accessToken;
  SessionUserRole role = SessionUserRole.client;

  // Server avatar URL can be unavailable in prototype flow before first login.
  String? localAvatarPath;
  String? pendingAvatarUploadPath;

  Future<void> setAuth({required String token, required SessionUserRole userRole}) async {
    accessToken = token;
    role = userRole;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    await prefs.setString(_roleKey, userRole.name);
  }

  Future<bool> restoreAuth() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_tokenKey);
    if (token == null || token.trim().isEmpty) {
      return false;
    }
    accessToken = token.trim();
    role = _parseRole(prefs.getString(_roleKey));
    return true;
  }

  SessionUserRole _parseRole(String? value) {
    switch (value) {
      case 'master':
        return SessionUserRole.master;
      case 'moderator':
        return SessionUserRole.moderator;
      default:
        return SessionUserRole.client;
    }
  }

  void setLocalAvatarPath(String? path) {
    localAvatarPath = (path == null || path.trim().isEmpty) ? null : path;
  }

  void setPendingAvatarUploadPath(String? path) {
    pendingAvatarUploadPath = (path == null || path.trim().isEmpty) ? null : path;
  }

  void clearPendingAvatarUpload() {
    pendingAvatarUploadPath = null;
  }

  Future<void> clear() async {
    accessToken = null;
    role = SessionUserRole.client;
    localAvatarPath = null;
    pendingAvatarUploadPath = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_roleKey);
  }
}

enum SessionUserRole { client, master, moderator }
