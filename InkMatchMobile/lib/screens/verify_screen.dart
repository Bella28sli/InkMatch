import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../l10n/app_strings.dart';
import '../services/api_client.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class VerifyScreen extends StatefulWidget {
  const VerifyScreen({super.key});

  static const route = '/verify';

  @override
  State<VerifyScreen> createState() => _VerifyScreenState();
}

class _VerifyScreenState extends State<VerifyScreen> {
  final _formKey = GlobalKey<FormState>();
  final _loginCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();

  bool _loading = false;
  String? _error;
  bool _prefilled = false;
  String? _registrationToken;

  final _api = ApiClient.defaultClient();

  @override
  void dispose() {
    _loginCtrl.dispose();
    _codeCtrl.dispose();
    super.dispose();
  }

  void _tryPrefillLogin() {
    if (_prefilled) return;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is String && args.isNotEmpty) {
      _loginCtrl.text = args;
    } else if (args is Map) {
      final login = args['login'];
      final token = args['registration_token'];
      if (login is String && login.isNotEmpty) {
        _loginCtrl.text = login;
      }
      if (token is String && token.isNotEmpty) {
        _registrationToken = token;
      }
    }
    _prefilled = true;
  }

  Future<void> _requestCode() async {
    setState(() {
      _error = null;
      _loading = true;
    });

    try {
      final res = await _api.postJson('/auth/verify/request', {
        'login': _loginCtrl.text.trim(),
        if (_registrationToken != null) 'registration_token': _registrationToken,
      });
      if (!mounted) return;

      if (res.statusCode == 204) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppStrings.codeSent(context))),
        );
      } else {
        setState(() => _error = '${res.statusCode}');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _confirm() async {
    setState(() {
      _error = null;
      _loading = true;
    });

    try {
      final res = await _api.postJson('/auth/verify/confirm', {
        'login': _loginCtrl.text.trim(),
        'code': _codeCtrl.text.trim(),
        if (_registrationToken != null) 'registration_token': _registrationToken,
      });
      if (!mounted) return;

      if (res.statusCode == 204) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppStrings.verified(context))),
        );
        Navigator.pop(context);
      } else {
        setState(() => _error = '${res.statusCode}');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    _tryPrefillLogin();
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: constraints.maxHeight),
                    child: Form(
                      key: _formKey,
                      child: Column(
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
                          const SizedBox(height: 12),
                          Text(
                            AppStrings.verify(context),
                            style: TextStyle(
                              fontFamily: AppTypography.headerFont(locale),
                              fontSize: 24,
                              color: AppColors.accent,
                            ),
                          ),
                          const SizedBox(height: 16),
                          _PlainField(
                            label: AppStrings.emailOrPhone(context),
                            controller: _loginCtrl,
                            validator: (v) => (v == null || v.isEmpty)
                                ? AppStrings.errLogin(context)
                                : null,
                          ),
                          const SizedBox(height: 12),
                          _PlainField(
                            label: AppStrings.code(context),
                            controller: _codeCtrl,
                            validator: (v) => (v == null || v.isEmpty)
                                ? AppStrings.errCode(context)
                                : null,
                          ),
                          const SizedBox(height: 12),
                          if (_error != null)
                            Text(_error!, style: const TextStyle(color: Colors.red)),
                          const Spacer(),
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton(
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: AppColors.ink,
                                    side: const BorderSide(color: AppColors.ink),
                                    textStyle: TextStyle(
                                      fontFamily: AppTypography.bodyFont(locale),
                                    ),
                                  ),
                                  onPressed: _loading
                                      ? null
                                      : () {
                                          if (_formKey.currentState!.validate()) {
                                            _requestCode();
                                          }
                                        },
                                  child: Text(AppStrings.requestCode(context)),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.accent,
                                    foregroundColor: Colors.white,
                                    textStyle: TextStyle(
                                      fontFamily: AppTypography.bodyFont(locale),
                                    ),
                                  ),
                                  onPressed: _loading
                                      ? null
                                      : () {
                                          if (_formKey.currentState!.validate()) {
                                            _confirm();
                                          }
                                        },
                                  child: _loading
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(strokeWidth: 2),
                                        )
                                      : Text(AppStrings.confirm(context)),
                                ),
                              ),
                            ],
                          ),
                        ],
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

class _PlainField extends StatelessWidget {
  const _PlainField({
    required this.label,
    required this.controller,
    this.validator,
  });

  final String label;
  final TextEditingController controller;
  final String? Function(String?)? validator;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return TextFormField(
      controller: controller,
      validator: validator,
      cursorColor: AppColors.ink,
      style: TextStyle(
        color: AppColors.ink,
        fontFamily: AppTypography.bodyFont(locale),
      ),
      decoration: InputDecoration(
        labelText: label,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: AppColors.ink.withValues(alpha: 0.12)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: AppColors.ink.withValues(alpha: 0.12)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
        labelStyle: TextStyle(
          color: AppColors.inkSoft,
          fontFamily: AppTypography.bodyFont(locale),
        ),
      ),
    );
  }
}
