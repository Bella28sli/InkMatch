import 'dart:convert';
import 'dart:io';

import 'package:http_parser/http_parser.dart';

import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../services/push_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../l10n/app_locale_scope.dart';
import '../l10n/app_strings.dart';
import 'feed_demo_screen.dart';
import 'register_screen.dart';
import 'moderation_queue_screen.dart';
import 'forgot_password_screen.dart';
import 'master_verification_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  static const route = '/login';

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _loginCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();

  bool _loading = false;
  String? _error;

  final _api = ApiClient.defaultClient();

  @override
  void dispose() {
    _loginCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  bool _isValidEmail(String value) {
    final email = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    return email.hasMatch(value);
  }

  bool _isValidPhone(String value) {
    final normalized = value.replaceAll(RegExp(r'[^0-9+]'), '');
    final phone = RegExp(r'^\+?[0-9]{10,15}$');
    return phone.hasMatch(normalized);
  }

  SessionUserRole _parseRoleFromAccessToken(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return SessionUserRole.client;
      final payload = utf8.decode(
        base64Url.decode(base64Url.normalize(parts[1])),
      );
      final data = jsonDecode(payload);
      final role = data is Map<String, dynamic>
          ? data['role']?.toString()
          : null;
      if (role == 'master') return SessionUserRole.master;
      if (role == 'moderator') return SessionUserRole.moderator;
      return SessionUserRole.client;
    } catch (_) {
      return SessionUserRole.client;
    }
  }

  Future<void> _uploadPendingAvatarIfAny() async {
    final pendingPath = AppSession.instance.pendingAvatarUploadPath;
    if (pendingPath == null || pendingPath.isEmpty) return;
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;

    final file = File(pendingPath);
    if (!file.existsSync()) {
      AppSession.instance.clearPendingAvatarUpload();
      return;
    }

    try {
      final res = await _api.postMultipart(
        '/profiles/me/avatar',
        file: file,
        fieldName: 'file',
        contentType: file.path.toLowerCase().endsWith('.png')
            ? MediaType('image', 'png')
            : file.path.toLowerCase().endsWith('.webp')
                ? MediaType('image', 'webp')
                : MediaType('image', 'jpeg'),
        accessToken: token,
      );
      if (res.statusCode == 200) {
        AppSession.instance.clearPendingAvatarUpload();
      }
    } catch (_) {
      // Non-blocking: avatar can be uploaded later from profile edit.
    }
  }

  bool _validate() {
    final login = _loginCtrl.text.trim();
    final password = _passwordCtrl.text;

    if (login.isEmpty) {
      setState(() => _error = AppStrings.errLogin(context));
      return false;
    }

    if (login.contains('@')) {
      if (!_isValidEmail(login)) {
        setState(() => _error = AppStrings.errEmailInvalid(context));
        return false;
      }
    } else {
      if (!_isValidPhone(login)) {
        setState(() => _error = AppStrings.errPhoneInvalid(context));
        return false;
      }
    }

    if (password.isEmpty) {
      setState(() => _error = AppStrings.errPassword(context));
      return false;
    }
    return true;
  }

  Future<void> _login() async {
    setState(() {
      _error = null;
      _loading = true;
    });

    try {
      final res = await _api.postJson('/auth/login', {
        'login': _loginCtrl.text.trim(),
        'password': _passwordCtrl.text,
      });

      if (!mounted) return;

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final accessToken = data['access_token']?.toString() ?? '';
        if (accessToken.isNotEmpty) {
          await AppSession.instance.setAuth(
            token: accessToken,
            userRole: _parseRoleFromAccessToken(accessToken),
          );
          await PushService.instance.registerCurrentDeviceToken();
          await _uploadPendingAvatarIfAny();
        }
        var targetRoute = AppSession.instance.role == SessionUserRole.moderator
            ? ModerationQueueScreen.route
            : FeedDemoScreen.route;
        if (AppSession.instance.role == SessionUserRole.master) {
          try {
            final profileRes = await _api.getJson(
              '/profiles/me/full',
              accessToken: accessToken,
            );
            if (profileRes.statusCode == 200) {
              final profile =
                  jsonDecode(profileRes.body) as Map<String, dynamic>;
              if ((profile['is_verified'] ?? false) != true) {
                targetRoute = MasterVerificationScreen.route;
              }
            }
          } catch (_) {
            // Non-blocking: the profile banner still offers verification.
          }
        }
        Navigator.pushNamedAndRemoveUntil(
          context,
          targetRoute,
          (route) => false,
        );
      } else {
        setState(() {
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppStrings.errValidation(context),
          );
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = ApiErrorMapper.mapException(context, e));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/img/bg_light.png', fit: BoxFit.cover),
          Container(color: AppColors.ink.withOpacity(0.05)),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                return SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 16,
                  ),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      minHeight: constraints.maxHeight,
                    ),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 360),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Align(
                              alignment: Alignment.topRight,
                              child: TextButton(
                                onPressed: AppLocaleScope.of(context).toggle,
                                child: Text(
                                  locale.languageCode.toUpperCase(),
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    color: AppColors.ink,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              AppStrings.title(context),
                              style: TextStyle(
                                fontFamily: AppTypography.headerFont(locale),
                                fontSize: 38,
                                color: AppColors.ink,
                                letterSpacing: 1.6,
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              AppStrings.signIn(context),
                              style: TextStyle(
                                fontFamily: AppTypography.headerFont(locale),
                                fontSize: 24,
                                color: AppColors.accent,
                              ),
                            ),
                            const SizedBox(height: 16),
                            if (_error != null)
                              Container(
                                width: double.infinity,
                                margin: const EdgeInsets.only(bottom: 12),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 10,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.red.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(color: Colors.red),
                                ),
                                child: Text(
                                  _error!,
                                  style: TextStyle(
                                    color: Colors.red.shade900,
                                    fontFamily: AppTypography.bodyFont(locale),
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ),
                            _InkBarField(
                              label: AppStrings.emailOrPhone(context),
                              controller: _loginCtrl,
                            ),
                            const SizedBox(height: 12),
                            _InkBarField(
                              label: AppStrings.password(context),
                              controller: _passwordCtrl,
                              obscureText: true,
                            ),
                            const SizedBox(height: 12),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.accent,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 14,
                                  ),
                                  textStyle: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    fontSize: 18,
                                  ),
                                ),
                                onPressed: _loading
                                    ? null
                                    : () {
                                        if (_validate()) {
                                          _login();
                                        }
                                      },
                                child: _loading
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : Text(AppStrings.signIn(context)),
                              ),
                            ),
                            TextButton(
                              onPressed: _loading
                                  ? null
                                  : () => Navigator.pushNamed(
                                      context,
                                      ForgotPasswordScreen.route,
                                    ),
                              child: Text(
                                AppStrings.forgotPassword(context),
                                style: TextStyle(
                                  fontFamily: AppTypography.bodyFont(locale),
                                  color: AppColors.ink,
                                ),
                              ),
                            ),
                            TextButton(
                              onPressed: _loading
                                  ? null
                                  : () => Navigator.pushNamed(
                                      context,
                                      RegisterScreen.route,
                                    ),
                              child: Text(
                                AppStrings.signUp(context),
                                style: TextStyle(
                                  fontFamily: AppTypography.bodyFont(locale),
                                  color: AppColors.accent,
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _InkBarField extends StatelessWidget {
  const _InkBarField({
    required this.label,
    required this.controller,
    this.obscureText = false,
  });

  final String label;
  final TextEditingController controller;
  final bool obscureText;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      cursorColor: AppColors.ink,
      style: TextStyle(
        color: AppColors.ink,
        fontFamily: AppTypography.bodyFont(locale),
      ),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: TextStyle(
          color: AppColors.inkSoft,
          fontFamily: AppTypography.bodyFont(locale),
        ),
      ),
    );
  }
}
