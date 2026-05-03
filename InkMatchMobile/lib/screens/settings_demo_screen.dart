import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'activity_center_screen.dart';
import 'feed_settings_screen.dart';
import 'forgot_password_screen.dart';
import 'inkmatch_defaults_screen.dart';
import 'login_screen.dart';
import 'moderation_queue_screen.dart';
import 'moderation_stats_screen.dart';
import 'restriction_history_screen.dart';

enum SettingsRole { client, master, moderator }

class SettingsScreenArgs {
  const SettingsScreenArgs({required this.role});

  final SettingsRole role;
}

class SettingsDemoScreen extends StatefulWidget {
  const SettingsDemoScreen({super.key});

  static const route = '/demo-settings';

  @override
  State<SettingsDemoScreen> createState() => _SettingsDemoScreenState();
}

class _SettingsDemoScreenState extends State<SettingsDemoScreen> {
  final _api = ApiClient.defaultClient();

  Map<String, dynamic>? _account;
  bool _notifyMessages = true;
  bool _notifyComments = true;
  bool _notifyLikes = true;
  bool _notifySubscriptions = true;
  bool _accountLoading = false;

  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  @override
  void initState() {
    super.initState();
    _loadAccount();
  }

  Future<void> _loadAccount() async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;
    setState(() => _accountLoading = true);
    try {
      final res = await _api.getJson('/account/me', accessToken: token);
      if (!mounted) return;
      if (res.statusCode == 200) {
        setState(() {
          _account = Map<String, dynamic>.from(jsonDecode(res.body) as Map);
        });
      }
    } catch (_) {
      // no-op: account section remains hidden
    } finally {
      if (mounted) {
        setState(() => _accountLoading = false);
      }
    }
  }

  Future<void> _changePassword() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final oldCtrl = TextEditingController();
    final newCtrl = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_t(isRu, 'Смена пароля', 'Change password')),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: oldCtrl,
              obscureText: true,
              decoration: InputDecoration(
                labelText: _t(isRu, 'Старый пароль', 'Old password'),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: newCtrl,
              obscureText: true,
              decoration: InputDecoration(
                labelText: _t(isRu, 'Новый пароль', 'New password'),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(_t(isRu, 'Отмена', 'Cancel')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(_t(isRu, 'Сохранить', 'Save')),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;

    try {
      final res = await _api.postJson('/account/me/change-password', {
        'old_password': oldCtrl.text,
        'new_password': newCtrl.text,
      }, accessToken: token);
      if (!mounted) return;
      final msg = res.statusCode == 204
          ? _t(isRu, 'Пароль успешно изменен', 'Password changed')
          : ApiErrorMapper.mapHttpError(
              context,
              res.statusCode,
              res.body,
              fallback: _t(
                isRu,
                'Не удалось изменить пароль',
                'Failed to change password',
              ),
            );
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiErrorMapper.mapException(context, e))),
      );
    }
  }

  Future<void> _bindContact(String type) async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final ctrl = TextEditingController();
    final isEmail = type == 'email';

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          _t(
            isRu,
            isEmail ? 'Привязать email' : 'Привязать телефон',
            isEmail ? 'Bind email' : 'Bind phone',
          ),
        ),
        content: TextField(
          controller: ctrl,
          keyboardType: isEmail
              ? TextInputType.emailAddress
              : TextInputType.phone,
          decoration: InputDecoration(
            labelText: _t(
              isRu,
              isEmail ? 'Email' : 'Телефон',
              isEmail ? 'Email' : 'Phone',
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(_t(isRu, 'Отмена', 'Cancel')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(_t(isRu, 'Сохранить', 'Save')),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    final payload = isEmail
        ? {'email': ctrl.text.trim()}
        : {'phone': ctrl.text.trim()};

    try {
      final res = await _api.patchJson(
        '/account/me',
        payload,
        accessToken: token,
      );
      if (!mounted) return;
      if (res.statusCode == 200) {
        await _loadAccount();
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _t(isRu, 'Контакт успешно добавлен', 'Contact added'),
            ),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              ApiErrorMapper.mapHttpError(
                context,
                res.statusCode,
                res.body,
                fallback: _t(
                  isRu,
                  'Не удалось сохранить контакт',
                  'Failed to save contact',
                ),
              ),
            ),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ApiErrorMapper.mapException(context, e))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final args = ModalRoute.of(context)?.settings.arguments;
    final fallbackRole = AppSession.instance.role == SessionUserRole.master
        ? SettingsRole.master
        : AppSession.instance.role == SessionUserRole.moderator
        ? SettingsRole.moderator
        : SettingsRole.client;
    final role = args is SettingsScreenArgs ? args.role : fallbackRole;

    final email = _account?['email']?.toString().trim() ?? '';
    final phone = _account?['phone']?.toString().trim() ?? '';
    final emailMissing = email.isEmpty;
    final phoneMissing = phone.isEmpty;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        title: Text(
          _t(isRu, 'Настройки', 'Settings'),
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SectionBlock(
            title: _t(isRu, 'Язык приложения', 'App language'),
            children: [
              _ActionRow(
                title: _t(isRu, 'Текущий язык', 'Current language'),
                subtitle: locale.languageCode == 'ru' ? 'Русский' : 'English',
                actionLabel: _t(isRu, 'Сменить', 'Toggle'),
                onTap: AppLocaleScope.of(context).toggle,
              ),
            ],
          ),
          if (role == SettingsRole.client)
            _SectionBlock(
              title: _t(
                isRu,
                'Предпочтения подбора мастеров',
                'Master matching preferences',
              ),
              children: [
                _ActionRow(
                  title: _t(isRu, 'Стили и теги ленты', 'Feed styles and tags'),
                  subtitle: _t(
                    isRu,
                    'Влияют на рекомендации',
                    'Affects recommendations',
                  ),
                  actionLabel: _t(isRu, 'Открыть', 'Open'),
                  onTap: () =>
                      Navigator.pushNamed(context, FeedPreferencesScreen.route),
                ),
                _ActionRow(
                  title: _t(
                    isRu,
                    'Базовые параметры InkMatch',
                    'InkMatch defaults',
                  ),
                  subtitle: _t(
                    isRu,
                    'Шаблон для новой заявки',
                    'Template for new requests',
                  ),
                  actionLabel: _t(isRu, 'Открыть', 'Open'),
                  onTap: () => Navigator.pushNamed(
                    context,
                    InkmatchDefaultsScreen.route,
                  ),
                ),
              ],
            ),
          if (role == SettingsRole.moderator)
            _SectionBlock(
              title: _t(isRu, 'Инструменты модератора', 'Moderator tools'),
              children: [
                _ActionRow(
                  title: _t(isRu, 'Очередь модерации', 'Moderation queue'),
                  subtitle: _t(
                    isRu,
                    'Жалобы и новые посты',
                    'Complaints and new posts',
                  ),
                  actionLabel: _t(isRu, 'Открыть', 'Open'),
                  onTap: () =>
                      Navigator.pushNamed(context, ModerationQueueScreen.route),
                ),
                _ActionRow(
                  title: _t(isRu, 'Статистика модерации', 'Moderation stats'),
                  subtitle: _t(isRu, 'Отчеты и экспорт', 'Reports and export'),
                  actionLabel: _t(isRu, 'Открыть', 'Open'),
                  onTap: () =>
                      Navigator.pushNamed(context, ModerationStatsScreen.route),
                ),
              ],
            ),
          _SectionBlock(
            title: _t(isRu, 'Уведомления', 'Notifications'),
            children: [
              _SwitchRow(
                title: _t(isRu, 'Сообщения', 'Messages'),
                value: _notifyMessages,
                onChanged: (v) => setState(() => _notifyMessages = v),
              ),
              _SwitchRow(
                title: _t(isRu, 'Комментарии и ответы', 'Comments and replies'),
                value: _notifyComments,
                onChanged: (v) => setState(() => _notifyComments = v),
              ),
              _SwitchRow(
                title: _t(isRu, 'Лайки и сохранения', 'Likes and saves'),
                value: _notifyLikes,
                onChanged: (v) => setState(() => _notifyLikes = v),
              ),
              _SwitchRow(
                title: _t(isRu, 'Новые подписчики', 'New followers'),
                value: _notifySubscriptions,
                onChanged: (v) => setState(() => _notifySubscriptions = v),
              ),
            ],
          ),
          if (role != SettingsRole.moderator)
            _SectionBlock(
              title: _t(isRu, 'Центр активности', 'Activity center'),
              children: [
                _ActionRow(
                  title: _t(isRu, 'Личная статистика', 'Personal analytics'),
                  subtitle: _t(isRu, 'Графики активности', 'Activity charts'),
                  actionLabel: _t(isRu, 'Открыть', 'Open'),
                  onTap: () =>
                      Navigator.pushNamed(context, ActivityCenterScreen.route),
                ),
              ],
            ),
          _SectionBlock(
            title: _t(isRu, 'Аккаунт', 'Account'),
            children: [
              _ActionRow(
                title: _t(isRu, 'История ограничений', 'Restriction history'),
                subtitle: _t(
                  isRu,
                  'Блокировки, ограничения и возможность апелляции',
                  'Blocks, restrictions and appeal option',
                ),
                actionLabel: _t(isRu, 'Открыть', 'Open'),
                onTap: () => Navigator.pushNamed(
                  context,
                  RestrictionHistoryScreen.route,
                ),
              ),
              if (_accountLoading)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _t(isRu, 'Загрузка аккаунта...', 'Loading account...'),
                      ),
                    ],
                  ),
                ),
              _ActionRow(
                title: _t(isRu, 'Сменить пароль', 'Change password'),
                subtitle: _t(
                  isRu,
                  'Подтверждение текущим паролем',
                  'Confirm with current password',
                ),
                actionLabel: _t(isRu, 'Открыть', 'Open'),
                onTap: _changePassword,
              ),
              _ActionRow(
                title: _t(isRu, 'Сброс пароля', 'Reset password'),
                subtitle: _t(
                  isRu,
                  'Если вы забыли пароль, отправим ссылку на почту',
                  'If forgotten, send reset link by email',
                ),
                actionLabel: _t(isRu, 'Перейти', 'Open'),
                onTap: () =>
                    Navigator.pushNamed(context, ForgotPasswordScreen.route),
              ),
              if (emailMissing)
                _ActionRow(
                  title: _t(isRu, 'Привязать email', 'Bind email'),
                  subtitle: _t(
                    isRu,
                    'Электронная почта не указана',
                    'Email is missing',
                  ),
                  actionLabel: _t(isRu, 'Добавить', 'Add'),
                  onTap: () => _bindContact('email'),
                ),
              if (phoneMissing)
                _ActionRow(
                  title: _t(isRu, 'Привязать телефон', 'Bind phone'),
                  subtitle: _t(
                    isRu,
                    'Номер телефона не указан',
                    'Phone is missing',
                  ),
                  actionLabel: _t(isRu, 'Добавить', 'Add'),
                  onTap: () => _bindContact('phone'),
                ),
              _ActionRow(
                title: _t(isRu, 'Выйти из аккаунта', 'Sign out'),
                subtitle: _t(
                  isRu,
                  'Сбросить текущую сессию',
                  'Clear current session',
                ),
                actionLabel: _t(isRu, 'Выйти', 'Sign out'),
                onTap: () {
                  AppSession.instance.clear();
                  Navigator.pushNamedAndRemoveUntil(
                    context,
                    LoginScreen.route,
                    (route) => false,
                  );
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionBlock extends StatelessWidget {
  const _SectionBlock({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              color: AppColors.ink,
              fontSize: 20,
            ),
          ),
          const SizedBox(height: 8),
          ...children,
        ],
      ),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.title,
    required this.value,
    required this.onChanged,
  });

  final String title;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return SwitchListTile(
      value: value,
      onChanged: onChanged,
      contentPadding: EdgeInsets.zero,
      activeThumbColor: AppColors.accent,
      title: Text(
        title,
        style: TextStyle(
          fontFamily: AppTypography.bodyFont(locale),
          color: AppColors.ink,
        ),
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.title,
    required this.subtitle,
    required this.actionLabel,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final String actionLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontFamily: AppTypography.bodyFont(locale),
                    color: AppColors.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontFamily: AppTypography.bodyFont(locale),
                    color: AppColors.ink.withValues(alpha: 0.75),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          TextButton(onPressed: onTap, child: Text(actionLabel)),
        ],
      ),
    );
  }
}
