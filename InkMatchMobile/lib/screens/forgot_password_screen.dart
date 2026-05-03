import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../l10n/app_strings.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  static const route = '/forgot-password';

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _emailCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _api = ApiClient.defaultClient();

  bool _loadingRequest = false;
  bool _loadingConfirm = false;
  String? _error;
  String? _message;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _codeCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  String _extractOobCode(String input) {
    final value = input.trim();
    if (value.contains('oobCode=')) {
      final uri = Uri.tryParse(value);
      final code = uri?.queryParameters['oobCode'];
      if (code != null && code.isNotEmpty) return code;
    }
    return value;
  }

  bool _isPasswordStrong(String value) {
    final hasLower = RegExp(r'[a-z]').hasMatch(value);
    final hasUpper = RegExp(r'[A-Z]').hasMatch(value);
    return hasLower && hasUpper;
  }

  bool _validateEmail() {
    final email = _emailCtrl.text.trim();
    final re = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    if (email.isEmpty || !re.hasMatch(email)) {
      setState(() => _error = AppStrings.errEmailInvalid(context));
      return false;
    }
    return true;
  }

  Future<void> _requestReset() async {
    if (!_validateEmail()) return;
    setState(() {
      _loadingRequest = true;
      _error = null;
      _message = null;
    });

    try {
      final res = await _api.postJson('/auth/password/reset-request', {
        'email': _emailCtrl.text.trim(),
      });
      if (!mounted) return;
      if (res.statusCode == 204) {
        setState(() => _message = AppStrings.passwordResetSent(context));
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
      if (mounted) setState(() => _loadingRequest = false);
    }
  }

  Future<void> _confirmReset() async {
    if (!_validateEmail()) return;
    final code = _extractOobCode(_codeCtrl.text);
    if (code.isEmpty) {
      setState(() => _error = AppStrings.errResetCode(context));
      return;
    }
    if (_passwordCtrl.text.length < 8) {
      setState(() => _error = AppStrings.errPasswordShort(context));
      return;
    }
    if (!_isPasswordStrong(_passwordCtrl.text)) {
      setState(() => _error = AppStrings.errPasswordCase(context));
      return;
    }

    setState(() {
      _loadingConfirm = true;
      _error = null;
      _message = null;
    });

    try {
      final res = await _api.postJson('/auth/password/reset-confirm', {
        'oob_code': code,
        'new_password': _passwordCtrl.text,
      });
      if (!mounted) return;
      if (res.statusCode == 204) {
        setState(() => _message = AppStrings.passwordResetDone(context));
        await Future<void>.delayed(const Duration(milliseconds: 800));
        if (!mounted) return;
        Navigator.pop(context);
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
      if (mounted) setState(() => _loadingConfirm = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final loading = _loadingRequest || _loadingConfirm;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          AppStrings.resetPassword(context),
          style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
        ),
      ),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/img/bg_light.png', fit: BoxFit.cover),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  if (_error != null) _MessageBox(text: _error!, isError: true),
                  if (_message != null)
                    _MessageBox(text: _message!, isError: false),
                  _InkField(
                    label: AppStrings.email(context),
                    controller: _emailCtrl,
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: loading ? null : _requestReset,
                      child: _loadingRequest
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(AppStrings.sendResetEmail(context)),
                    ),
                  ),
                  const SizedBox(height: 18),
                  _InkField(
                    label: AppStrings.resetCode(context),
                    controller: _codeCtrl,
                  ),
                  const SizedBox(height: 12),
                  _InkField(
                    label: AppStrings.newPassword(context),
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
                      ),
                      onPressed: loading ? null : _confirmReset,
                      child: _loadingConfirm
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(AppStrings.resetPassword(context)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _InkField extends StatelessWidget {
  const _InkField({
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

class _MessageBox extends StatelessWidget {
  const _MessageBox({required this.text, required this.isError});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: isError
            ? Colors.red.withValues(alpha: 0.12)
            : Colors.green.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: isError ? Colors.red : Colors.green),
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: TextStyle(
          color: isError ? Colors.red.shade900 : Colors.green.shade900,
          fontFamily: AppTypography.bodyFont(locale),
        ),
      ),
    );
  }
}
