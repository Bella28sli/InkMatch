import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/avatar_picker.dart';
import '../l10n/app_locale_scope.dart';
import '../l10n/app_strings.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'location_picker_screen.dart';
import 'login_screen.dart';

enum RegisterMethod { email, phone }

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  static const route = '/register';

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _pageCtrl = PageController();
  int _step = 0;
  bool _loading = false;
  String? _error;

  final _nicknameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _password2Ctrl = TextEditingController();
  final _experienceCtrl = TextEditingController();

  String _role = 'client';
  RegisterMethod _registerMethod = RegisterMethod.email;
  File? _avatarFile;
  LocationPickerResult? _registrationLocation;
  bool _showPassword = false;
  bool _showPassword2 = false;

  final _api = ApiClient.defaultClient();

  final _styleSelection = <String>{};
  final _tagSelection = <String>{};

  final _styleOptions = const <_SelectOption>[
    _SelectOption('abstract', 'assets/styles/abstract.jpg'),
    _SelectOption('blackgray', 'assets/styles/blackgray.jpg'),
    _SelectOption('blackwork', 'assets/styles/blackwork.jpg'),
    _SelectOption('fineline', 'assets/styles/fineline.jpg'),
    _SelectOption('nature', 'assets/styles/nature.jpg'),
    _SelectOption('neotrad', 'assets/styles/neotrad.jpg'),
    _SelectOption('oldschool', 'assets/styles/oldschool.jpg'),
    _SelectOption('realism', 'assets/styles/realism.jpg'),
    _SelectOption('trashpolka', 'assets/styles/trashpolka.jpg'),
  ];

  final _tagOptions = const <_SelectOption>[
    _SelectOption('animals', 'assets/tags/animals.jpg'),
    _SelectOption('anime', 'assets/tags/anime.jpg'),
    _SelectOption('cyberpunk', 'assets/tags/cyberpunk.jpg'),
    _SelectOption('flowers', 'assets/tags/flowers.jpg'),
    _SelectOption('gothic', 'assets/tags/gothic.jpg'),
    _SelectOption('lettering', 'assets/tags/lettering.jpg'),
    _SelectOption('mini', 'assets/tags/mini.jpg'),
    _SelectOption('ornamental', 'assets/tags/ornamental.jpg'),
    _SelectOption('zodiac', 'assets/tags/zodiac.jpg'),
  ];

  @override
  void dispose() {
    _pageCtrl.dispose();
    _nicknameCtrl.dispose();
    _emailCtrl.dispose();
    _phoneCtrl.dispose();
    _passwordCtrl.dispose();
    _password2Ctrl.dispose();
    _experienceCtrl.dispose();
    super.dispose();
  }

  int get _maxStep => _role == 'master' ? 5 : 4;
  int get _addressStep => _role == 'master' ? 3 : 2;
  int get _styleStep => _role == 'master' ? 4 : 3;
  int get _tagStep => _role == 'master' ? 5 : 4;

  bool _isValidEmail(String value) {
    final email = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    return email.hasMatch(value);
  }

  bool _isValidPhone(String value) {
    final normalized = value.replaceAll(RegExp(r'[^0-9+]'), '');
    final phone = RegExp(r'^\+?[0-9]{10,15}$');
    return phone.hasMatch(normalized);
  }

  bool _isPasswordStrong(String value) {
    final hasLower = RegExp(r'[a-z]').hasMatch(value);
    final hasUpper = RegExp(r'[A-Z]').hasMatch(value);
    return hasLower && hasUpper;
  }

  Future<bool> _checkNicknameAvailable() async {
    final nickname = _nicknameCtrl.text.trim();
    if (nickname.length < 2 || nickname.length > 64) return false;
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    try {
      final res = await _api.getJson(
        '/auth/nickname-available',
        query: {'nickname': nickname},
      );
      if (!mounted) return false;
      if (res.statusCode != 200) {
        setState(
          () => _error = isRu
              ? 'Не удалось проверить никнейм'
              : 'Could not check nickname',
        );
        return false;
      }
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      if (data['available'] == true) return true;
      setState(
        () => _error = isRu ? 'Никнейм уже занят' : 'Nickname is already taken',
      );
      return false;
    } catch (_) {
      setState(
        () => _error = isRu
            ? 'Не удалось проверить никнейм'
            : 'Could not check nickname',
      );
      return false;
    }
  }

  bool _validateCurrentStep() {
    if (_step == 0) {
      final nickname = _nicknameCtrl.text.trim();
      if (nickname.length < 2 || nickname.length > 64) {
        setState(() => _error = AppStrings.errNickname(context));
        return false;
      }
    }

    if (_step == 1) {
      final password = _passwordCtrl.text;
      final password2 = _password2Ctrl.text;

      if (_registerMethod == RegisterMethod.email) {
        final email = _emailCtrl.text.trim();
        if (email.isEmpty) {
          setState(() => _error = AppStrings.errNeedLogin(context));
          return false;
        }
        if (!_isValidEmail(email)) {
          setState(() => _error = AppStrings.errEmailInvalid(context));
          return false;
        }
      } else {
        final phone = _phoneCtrl.text.trim();
        if (phone.isEmpty) {
          setState(() => _error = AppStrings.errNeedLogin(context));
          return false;
        }
        if (!_isValidPhone(phone)) {
          setState(() => _error = AppStrings.errPhoneInvalid(context));
          return false;
        }
      }

      if (password.isEmpty) {
        setState(() => _error = AppStrings.errPassword(context));
        return false;
      }
      if (password.length < 8) {
        setState(() => _error = AppStrings.errPasswordShort(context));
        return false;
      }
      if (!_isPasswordStrong(password)) {
        setState(() => _error = AppStrings.errPasswordCase(context));
        return false;
      }
      if (password2.isEmpty) {
        setState(() => _error = AppStrings.errRepeatPassword(context));
        return false;
      }
      if (password != password2) {
        setState(() => _error = AppStrings.errPasswordMismatch(context));
        return false;
      }
    }

    if (_step == 2 && _role == 'master') {
      final years = int.tryParse(_experienceCtrl.text.trim());
      if (years == null || years < 1 || years > 60) {
        setState(() => _error = AppStrings.errExperience(context));
        return false;
      }
    }

    if (_step == _addressStep &&
        _role == 'master' &&
        _registrationLocation == null) {
      setState(
        () => _error =
            'РЈРєР°Р¶РёС‚Рµ Р°РґСЂРµСЃ РІР°С€РµР№ С‚Р°С‚Сѓ-СЃС‚СѓРґРёРё',
      );
      return false;
    }

    if (_step == _styleStep && _styleSelection.length != 3) {
      setState(() => _error = AppStrings.errPick3Styles(context));
      return false;
    }

    if (_step == _tagStep && _tagSelection.length != 3) {
      setState(() => _error = AppStrings.errPick3Tags(context));
      return false;
    }

    return true;
  }

  Future<void> _pickAvatar() async {
    final source = await AvatarPicker.chooseSource(context);
    if (source == null) return;
    final file = await AvatarPicker.pickAndCrop(context, source: source);
    if (file == null) return;
    setState(() => _avatarFile = file);
  }

  Future<void> _next() async {
    setState(() => _error = null);

    if (!_validateCurrentStep()) return;

    if (_step == 0) {
      if (!await _checkNicknameAvailable()) return;
    }

    if (_step < _maxStep) {
      _pageCtrl.nextPage(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    } else {
      _register();
    }
  }

  void _back() {
    if (_step == 0) {
      Navigator.pop(context);
      return;
    }
    _pageCtrl.previousPage(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  Future<void> _register() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final email = _registerMethod == RegisterMethod.email
        ? _emailCtrl.text.trim()
        : null;
    final phone = _registerMethod == RegisterMethod.phone
        ? _phoneCtrl.text.trim()
        : null;

    final payload = <String, dynamic>{
      'email': email?.isEmpty == true ? null : email,
      'phone': phone?.isEmpty == true ? null : phone,
      'password': _passwordCtrl.text,
      'role': _role,
      'profile': {
        'nickname': _nicknameCtrl.text.trim(),
        'home_location_id': _role == 'client'
            ? _registrationLocation?.id
            : null,
      },
      'preferred_style_ids': _styleSelection.toList(),
      'preferred_tag_ids': _tagSelection.toList(),
    };

    if (_role == 'master') {
      payload['master_profile'] = {
        'experience_years': int.tryParse(_experienceCtrl.text),
      };
      final selectedMetro =
          _registrationLocation?.location['selected_metro_station'] as Map?;
      payload['workplace'] = {
        'location_id': _registrationLocation?.id,
        'public_display_mode': selectedMetro == null ? 'street' : 'metro',
        'public_metro_station_id': selectedMetro?['id']?.toString(),
      };
    }

    try {
      final res = await _api.postJson('/auth/register', payload);
      if (!mounted) return;
      if (res.statusCode == 201) {
        if (!mounted) return;
        final responseData = jsonDecode(res.body) as Map<String, dynamic>;
        AppSession.instance.setLocalAvatarPath(_avatarFile?.path);
        AppSession.instance.setPendingAvatarUploadPath(_avatarFile?.path);
        final verificationLogin = email ?? phone ?? '';
        final requiresVerification = _registerMethod == RegisterMethod.email;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              requiresVerification
                  ? 'Check your code to finish registration'
                  : AppStrings.verified(context),
            ),
          ),
        );
        if (requiresVerification) {
          final registrationToken =
              responseData['registration_token'] as String?;
          if (registrationToken != null && registrationToken.isNotEmpty) {
            Navigator.pushReplacementNamed(
              context,
              VerifyScreen.route,
              arguments: {
                'login': verificationLogin,
                'registration_token': registrationToken,
              },
            );
            return;
          }
        }
        Navigator.pushReplacementNamed(context, LoginScreen.route);
      } else {
        setState(() {
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppStrings.errRegisterFailed(context),
          );
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = ApiErrorMapper.mapException(context, e));
    } finally {
      if (mounted) setState(() => _loading = false);
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
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
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
                  Text(
                    AppStrings.signUp(context),
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 26,
                      color: AppColors.accent,
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (_error != null)
                    Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 8),
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
                  Expanded(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 360),
                        child: PageView(
                          controller: _pageCtrl,
                          onPageChanged: (v) => setState(() => _step = v),
                          physics: const NeverScrollableScrollPhysics(),
                          children: [
                            _stepRole(),
                            _stepContacts(),
                            if (_role == 'master') _stepMaster(),
                            _stepAddress(),
                            _stepStyles(),
                            _stepTags(),
                          ],
                        ),
                      ),
                    ),
                  ),
                  Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 360),
                      child: Row(
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
                              onPressed: _loading ? null : _back,
                              child: Text(AppStrings.back(context)),
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
                              onPressed: _loading ? null : _next,
                              child: _loading
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : Text(
                                      _step == _maxStep
                                          ? AppStrings.finish(context)
                                          : AppStrings.next(context),
                                    ),
                            ),
                          ),
                        ],
                      ),
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

  Widget _stepRole() {
    return _StepScroll(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _RoleToggle(
            value: _role,
            onChanged: (v) => setState(() => _role = v),
            clientLabel: AppStrings.roleClient(context),
            masterLabel: AppStrings.roleMaster(context),
          ),
          const SizedBox(height: 16),
          _InkBarField(
            label: AppStrings.nickname(context),
            controller: _nicknameCtrl,
            required: true,
          ),
          const SizedBox(height: 16),
          GestureDetector(
            onTap: _pickAvatar,
            child: Container(
              width: 88,
              height: 88,
              decoration: const BoxDecoration(
                color: AppColors.ink,
                shape: BoxShape.circle,
              ),
              child: ClipOval(
                child: _avatarFile == null
                    ? Center(
                        child: Text(
                          AppStrings.avatar(context),
                          style: TextStyle(
                            fontFamily: AppTypography.bodyFont(
                              AppLocaleScope.of(context).locale,
                            ),
                            color: AppColors.background,
                          ),
                        ),
                      )
                    : Image.file(_avatarFile!, fit: BoxFit.cover),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _stepContacts() {
    return _StepScroll(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _RegisterMethodToggle(
            value: _registerMethod,
            onChanged: (method) {
              setState(() {
                _registerMethod = method;
                _error = null;
              });
            },
            emailLabel: AppStrings.regByEmail(context),
            phoneLabel: AppStrings.regByPhone(context),
          ),
          const SizedBox(height: 12),
          if (_registerMethod == RegisterMethod.email)
            _InkBarField(
              label: AppStrings.email(context),
              controller: _emailCtrl,
              required: true,
            )
          else
            _InkBarField(
              label: AppStrings.phone(context),
              controller: _phoneCtrl,
              required: true,
            ),
          const SizedBox(height: 8),
          _InkBarField(
            label: AppStrings.password(context),
            controller: _passwordCtrl,
            required: true,
            obscureText: !_showPassword,
            onToggleVisibility: () =>
                setState(() => _showPassword = !_showPassword),
          ),
          const SizedBox(height: 8),
          _InkBarField(
            label: AppStrings.repeatPassword(context),
            controller: _password2Ctrl,
            required: true,
            obscureText: !_showPassword2,
            onToggleVisibility: () =>
                setState(() => _showPassword2 = !_showPassword2),
          ),
        ],
      ),
    );
  }

  Widget _stepMaster() {
    return _StepScroll(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _InkBarField(
            label: AppStrings.experience(context),
            controller: _experienceCtrl,
            required: true,
            keyboardType: TextInputType.number,
          ),
        ],
      ),
    );
  }

  Future<void> _pickRegistrationLocation() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<LocationPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => LocationPickerScreen(
          title: _role == 'master'
              ? (isRu ? 'Адрес тату-студии' : 'Tattoo studio address')
              : (isRu ? 'Ваш адрес' : 'Your address'),
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      _registrationLocation = result;
    });
  }

  Widget _stepAddress() {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final locale = AppLocaleScope.of(context).locale;
    return _StepScroll(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            _role == 'master'
                ? (isRu
                      ? 'Укажите адрес вашей тату-студии'
                      : 'Enter your tattoo studio address')
                : (isRu
                      ? 'Вы также можете указать свой адрес для упрощения поиска мастера в дальнейшем'
                      : 'You can also add your address to simplify master search later'),
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              color: AppColors.ink,
            ),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _pickRegistrationLocation,
            icon: const Icon(Icons.place_outlined),
            label: Text(
              _registrationLocation?.label ??
                  (_role == 'master'
                      ? (isRu
                            ? 'Выбрать адрес студии'
                            : 'Choose studio address')
                      : (isRu ? 'Указать адрес' : 'Add address')),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (_role == 'client') ...[
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => _next(),
              child: Text(isRu ? 'Пропустить' : 'Skip'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _stepStyles() {
    return _StepScroll(
      child: _SelectionGrid(
        title: AppStrings.chooseStyles(context),
        options: _styleOptions,
        selected: _styleSelection,
        limit: 3,
      ),
    );
  }

  Widget _stepTags() {
    return _StepScroll(
      child: _SelectionGrid(
        title: AppStrings.chooseTags(context),
        options: _tagOptions,
        selected: _tagSelection,
        limit: 3,
      ),
    );
  }
}

class _StepScroll extends StatelessWidget {
  const _StepScroll({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          padding: const EdgeInsets.only(bottom: 12),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: child,
          ),
        );
      },
    );
  }
}

class _SelectionGrid extends StatefulWidget {
  const _SelectionGrid({
    required this.title,
    required this.options,
    required this.selected,
    required this.limit,
  });

  final String title;
  final List<_SelectOption> options;
  final Set<String> selected;
  final int limit;

  @override
  State<_SelectionGrid> createState() => _SelectionGridState();
}

class _SelectionGridState extends State<_SelectionGrid> {
  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Column(
      children: [
        Text(
          widget.title,
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
        const SizedBox(height: 12),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
          ),
          itemCount: widget.options.length,
          itemBuilder: (context, index) {
            final item = widget.options[index];
            final active = widget.selected.contains(item.key);
            return GestureDetector(
              onTap: () {
                setState(() {
                  if (active) {
                    widget.selected.remove(item.key);
                  } else if (widget.selected.length < widget.limit) {
                    widget.selected.add(item.key);
                  }
                });
              },
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.asset(item.assetPath, fit: BoxFit.cover),
                  ),
                  if (active)
                    Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.accent, width: 3),
                        color: AppColors.accent.withOpacity(0.15),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

class _RoleToggle extends StatelessWidget {
  const _RoleToggle({
    required this.value,
    required this.onChanged,
    required this.clientLabel,
    required this.masterLabel,
  });

  final String value;
  final ValueChanged<String> onChanged;
  final String clientLabel;
  final String masterLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.ink,
        borderRadius: BorderRadius.circular(24),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: [
          _RoleChip(
            label: clientLabel,
            active: value == 'client',
            onTap: () => onChanged('client'),
          ),
          _RoleChip(
            label: masterLabel,
            active: value == 'master',
            onTap: () => onChanged('master'),
          ),
        ],
      ),
    );
  }
}

class _RegisterMethodToggle extends StatelessWidget {
  const _RegisterMethodToggle({
    required this.value,
    required this.onChanged,
    required this.emailLabel,
    required this.phoneLabel,
  });

  final RegisterMethod value;
  final ValueChanged<RegisterMethod> onChanged;
  final String emailLabel;
  final String phoneLabel;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.ink,
        borderRadius: BorderRadius.circular(24),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: [
          _MethodChip(
            label: emailLabel,
            active: value == RegisterMethod.email,
            onTap: () => onChanged(RegisterMethod.email),
          ),
          _MethodChip(
            label: phoneLabel,
            active: value == RegisterMethod.phone,
            onTap: () => onChanged(RegisterMethod.phone),
          ),
        ],
      ),
    );
  }
}

class _RoleChip extends StatelessWidget {
  const _RoleChip({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: active ? AppColors.accent : Colors.transparent,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                color: active ? Colors.white : AppColors.background,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MethodChip extends StatelessWidget {
  const _MethodChip({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: active ? AppColors.accent : Colors.transparent,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                color: active ? Colors.white : AppColors.background,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _InkBarField extends StatelessWidget {
  const _InkBarField({
    required this.label,
    required this.controller,
    this.required = false,
    this.obscureText = false,
    this.keyboardType,
    this.onToggleVisibility,
  });

  final String label;
  final TextEditingController controller;
  final bool required;
  final bool obscureText;
  final TextInputType? keyboardType;
  final VoidCallback? onToggleVisibility;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (required)
          const Padding(
            padding: EdgeInsets.only(bottom: 2),
            child: Text('*', style: TextStyle(color: Colors.red, fontSize: 16)),
          ),
        TextFormField(
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
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
            suffixIcon: onToggleVisibility == null
                ? null
                : IconButton(
                    onPressed: onToggleVisibility,
                    icon: Icon(
                      obscureText ? Icons.visibility : Icons.visibility_off,
                      color: AppColors.inkSoft,
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}

class _SelectOption {
  const _SelectOption(this.key, this.assetPath);

  final String key;
  final String assetPath;
}
