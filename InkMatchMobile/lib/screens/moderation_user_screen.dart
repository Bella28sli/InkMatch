import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class ModerationUserScreenArgs {
  const ModerationUserScreenArgs({required this.userId});

  final String userId;
}

class ModerationUserScreen extends StatefulWidget {
  const ModerationUserScreen({super.key});

  static const route = '/moderation/user';

  @override
  State<ModerationUserScreen> createState() => _ModerationUserScreenState();
}

class _ModerationUserScreenState extends State<ModerationUserScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  bool _restrictionsLoading = false;
  String? _error;
  Map<String, dynamic>? _payload;
  List<Map<String, dynamic>> _restrictions = [];
  List<Map<String, dynamic>> _warnings = [];
  List<Map<String, dynamic>> _restrictionReasons = [];
  List<Map<String, dynamic>> _warningReasons = [];

  String? get _token => AppSession.instance.accessToken;
  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_payload != null || _error != null) return;
    _load();
  }

  Future<void> _load() async {
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is! ModerationUserScreenArgs) {
      setState(() {
        _loading = false;
        _error = 'Missing user id';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await _api.getJson('/moderation/users/${args.userId}', accessToken: _token);
      final restrictionsRes = await _api.getJson(
        '/moderation/users/${args.userId}/restrictions',
        accessToken: _token,
      );
      final warningsRes = await _api.getJson(
        '/moderation/users/${args.userId}/warnings',
        accessToken: _token,
      );
      final restrictionReasonsRes = await _api.getJson(
        '/moderation/reasons',
        accessToken: _token,
        query: const {'applies_to': 'restriction'},
      );
      final warningReasonsRes = await _api.getJson(
        '/moderation/reasons',
        accessToken: _token,
        query: const {'applies_to': 'warning'},
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }

      setState(() {
        _payload = jsonDecode(res.body) as Map<String, dynamic>;
        if (restrictionsRes.statusCode == 200) {
          _restrictions = (jsonDecode(restrictionsRes.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        }
        if (warningsRes.statusCode == 200) {
          _warnings = (jsonDecode(warningsRes.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        }
        if (restrictionReasonsRes.statusCode == 200) {
          _restrictionReasons = (jsonDecode(restrictionReasonsRes.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        }
        if (warningReasonsRes.statusCode == 200) {
          _warningReasons = (jsonDecode(warningReasonsRes.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        }
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _reloadRestrictions() async {
    final payload = _payload;
    if (payload == null) return;
    setState(() => _restrictionsLoading = true);
    try {
      final res = await _api.getJson(
        '/moderation/users/${payload['id']}/restrictions',
        accessToken: _token,
      );
      if (!mounted) return;
      if (res.statusCode == 200) {
        setState(() {
          _restrictions = (jsonDecode(res.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
        });
      }
    } finally {
      if (mounted) setState(() => _restrictionsLoading = false);
    }
  }

  String _restrictionLabel(bool isRu, String value) {
    return switch (value) {
      'full_block' => _t(isRu, 'Полная блокировка', 'Full block'),
      'chat_only_read' => _t(isRu, 'Чат только для чтения', 'Chat read-only'),
      'posting_disabled' => _t(isRu, 'Запрет публикаций', 'Posting disabled'),
      'commenting_disabled' => _t(isRu, 'Запрет комментариев', 'Commenting disabled'),
      'inkmatch_disabled' => _t(isRu, 'Запрет InkMatch', 'InkMatch disabled'),
      'profile_hidden' => _t(isRu, 'Профиль скрыт', 'Profile hidden'),
      _ => value,
    };
  }

  Future<void> _applyRestriction(bool isRu) async {
    final payload = _payload;
    if (payload == null) return;
    var type = 'posting_disabled';
    String? reasonId;
    final reasonCtrl = TextEditingController();
    final durationCtrl = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(_t(isRu, 'Ограничить пользователя', 'Restrict user')),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                value: type,
                decoration: InputDecoration(labelText: _t(isRu, 'Тип ограничения', 'Restriction type')),
                items: const [
                  'full_block',
                  'chat_only_read',
                  'posting_disabled',
                  'commenting_disabled',
                  'inkmatch_disabled',
                  'profile_hidden',
                ].map((value) {
                  return DropdownMenuItem(
                    value: value,
                    child: Text(_restrictionLabel(isRu, value)),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) setDialogState(() => type = value);
                },
              ),
              const SizedBox(height: 8),
              if (_restrictionReasons.isNotEmpty)
                DropdownButtonFormField<String>(
                  value: reasonId,
                  decoration: InputDecoration(labelText: _t(isRu, 'Причина из справочника', 'Reason from catalog')),
                  items: _restrictionReasons.map((row) {
                    return DropdownMenuItem<String>(
                      value: row['id']?.toString(),
                      child: Text(row['title']?.toString() ?? ''),
                    );
                  }).toList(),
                  onChanged: (value) {
                    setDialogState(() => reasonId = value);
                  },
                ),
              if (_restrictionReasons.isNotEmpty) const SizedBox(height: 8),
              TextField(
                controller: reasonCtrl,
                minLines: 2,
                maxLines: 4,
                decoration: InputDecoration(labelText: _t(isRu, 'Причина', 'Reason')),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: durationCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: _t(isRu, 'Срок в часах, пусто — бессрочно', 'Hours, empty for permanent'),
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
              child: Text(_t(isRu, 'Применить', 'Apply')),
            ),
          ],
        ),
      ),
    );
    if (ok != true || !mounted) return;

    final reason = reasonCtrl.text.trim();
    if (reason.isEmpty && reasonId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_t(isRu, 'Укажите причину', 'Enter a reason'))),
      );
      return;
    }
    final duration = int.tryParse(durationCtrl.text.trim());
    final res = await _api.postJson(
      '/moderation/users/${payload['id']}/restrictions',
      {
        'restriction_type': type,
        if (reason.isNotEmpty) 'reason': reason,
        if (reasonId != null) 'reason_id': reasonId,
        if (duration != null) 'duration_hours': duration,
      },
      accessToken: _token,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          res.statusCode == 201
              ? _t(isRu, 'Ограничение применено', 'Restriction applied')
              : '${res.statusCode}: ${res.body}',
        ),
      ),
    );
    if (res.statusCode == 201) {
      await _reloadRestrictions();
      await _load();
    }
  }

  Future<void> _warnUser(bool isRu) async {
    final payload = _payload;
    if (payload == null) return;
    final reasonCtrl = TextEditingController();
    String? reasonId;
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(isRu ? 'Предупредить пользователя' : 'Warn user'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_warningReasons.isNotEmpty)
                DropdownButtonFormField<String>(
                  value: reasonId,
                  decoration: InputDecoration(
                    labelText: isRu ? 'Причина из справочника' : 'Reason from catalog',
                  ),
                  items: _warningReasons.map((row) {
                    return DropdownMenuItem<String>(
                      value: row['id']?.toString(),
                      child: Text(row['title']?.toString() ?? ''),
                    );
                  }).toList(),
                  onChanged: (value) => setDialogState(() => reasonId = value),
                ),
              if (_warningReasons.isNotEmpty) const SizedBox(height: 8),
              TextField(
                controller: reasonCtrl,
                minLines: 2,
                maxLines: 4,
                decoration: InputDecoration(
                  labelText: isRu ? 'Комментарий к предупреждению' : 'Warning note',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(isRu ? 'Отмена' : 'Cancel'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(isRu ? 'Выдать' : 'Warn'),
            ),
          ],
        ),
      ),
    );
    if (ok != true) return;
    final res = await _api.postJson(
      '/moderation/users/${payload['id']}/warn',
      {
        if (reasonCtrl.text.trim().isNotEmpty) 'reason': reasonCtrl.text.trim(),
        if (reasonId != null) 'reason_id': reasonId,
      },
      accessToken: _token,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          res.statusCode == 200
              ? (isRu ? 'Предупреждение отправлено' : 'Warning sent')
              : '${res.statusCode}: ${res.body}',
        ),
      ),
    );
    if (res.statusCode == 200) {
      await _load();
    }
  }

  Future<void> _deactivateRestriction(Map<String, dynamic> row, bool isRu) async {
    final reasonCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_t(isRu, 'Снять ограничение', 'Deactivate restriction')),
        content: TextField(
          controller: reasonCtrl,
          decoration: InputDecoration(labelText: _t(isRu, 'Комментарий', 'Note')),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(_t(isRu, 'Отмена', 'Cancel')),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(_t(isRu, 'Снять', 'Deactivate')),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final res = await _api.postJson(
      '/moderation/restrictions/${row['id']}/deactivate',
      {'reason': reasonCtrl.text.trim()},
      accessToken: _token,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          res.statusCode == 200
              ? _t(isRu, 'Ограничение снято', 'Restriction deactivated')
              : '${res.statusCode}: ${res.body}',
        ),
      ),
    );
    if (res.statusCode == 200) {
      await _reloadRestrictions();
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(_t(isRu, 'Пользователь', 'User'), style: TextStyle(fontFamily: AppTypography.headerFont(locale))),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _buildContent(locale, isRu),
    );
  }

  Widget _buildContent(Locale locale, bool isRu) {
    final payload = _payload!;
    final profile = (payload['profile'] as Map<String, dynamic>? ?? <String, dynamic>{});
    final master = (payload['master_profile'] as Map<String, dynamic>? ?? <String, dynamic>{});
    final stats = (payload['stats'] as Map<String, dynamic>? ?? <String, dynamic>{});

    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: () => _applyRestriction(isRu),
                icon: const Icon(Icons.gpp_maybe_outlined),
                label: Text(_t(isRu, 'Ограничить пользователя', 'Restrict user')),
              ),
              OutlinedButton.icon(
                onPressed: () => _warnUser(isRu),
                icon: const Icon(Icons.warning_amber_outlined),
                label: Text(isRu ? 'Предупредить' : 'Warn'),
              ),
            ],
          ),
        ),
        _Section(
          title: _t(isRu, 'Аккаунт', 'Account'),
          children: [
            _kv('ID', payload['id']),
            _kv(_t(isRu, 'Роль', 'Role'), payload['role']),
            _kv('Email', payload['email']),
            _kv(_t(isRu, 'Телефон', 'Phone'), payload['phone']),
            _kv(_t(isRu, 'Верифицирован', 'Verified'), payload['is_verified']),
          ],
        ),
        _Section(
          title: _t(isRu, 'Профиль', 'Profile'),
          children: [
            _kv(_t(isRu, 'Никнейм', 'Nickname'), profile['nickname']),
            _kv(_t(isRu, 'О себе', 'Bio'), profile['bio']),
            _kv('Avatar URL', profile['avatar_url']),
            _kv(_t(isRu, 'Валюта', 'Currency'), profile['default_currency']),
          ],
        ),
        if (master.isNotEmpty)
          _Section(
            title: _t(isRu, 'Профиль мастера', 'Master profile'),
            children: [
              _kv(_t(isRu, 'Опыт (лет)', 'Experience years'), master['experience_years']),
              _kv(_t(isRu, 'Цена от', 'Price min'), master['price_min']),
              _kv(_t(isRu, 'Цена до', 'Price max'), master['price_max']),
              _kv(_t(isRu, 'Описание', 'Description'), master['description']),
              _kv(_t(isRu, 'Рейтинг', 'Rating'), master['rating_avg']),
              _kv(_t(isRu, 'Завершено сессий', 'Completed sessions'), master['completed_sessions_count']),
            ],
          ),
        _Section(
          title: _t(isRu, 'Базовая статистика', 'Base stats'),
          children: [
            _kv(_t(isRu, 'Подписчики', 'Followers'), stats['followers_count']),
            _kv(_t(isRu, 'Подписки', 'Following'), stats['following_count']),
            _kv(_t(isRu, 'Посты', 'Posts'), stats['sketches_count']),
            _kv(_t(isRu, 'Коллекции', 'Collections'), stats['collections_count']),
            _kv(_t(isRu, 'Комментарии', 'Comments'), stats['comments_count']),
            _kv(_t(isRu, 'Лайков поставлено', 'Likes given'), stats['likes_given_count']),
            _kv(_t(isRu, 'Чаты', 'Chats'), stats['chats_count']),
            _kv(_t(isRu, 'Сообщения', 'Messages'), stats['messages_count']),
            _kv(_t(isRu, 'Жалобы автора', 'Complaints authored'), stats['complaints_authored_count']),
            _kv(_t(isRu, 'Жалобы на пользователя', 'Complaints against'), stats['complaints_against_count']),
            _kv(_t(isRu, 'Активные ограничения', 'Active restrictions'), stats['active_restrictions_count']),
          ],
        ),
        _Section(
          title: _t(isRu, 'Ограничения', 'Restrictions'),
          children: [
            Text(
              _t(isRu, 'Предупреждения', 'Warnings'),
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            if (_warnings.isEmpty)
              Text(
                _t(isRu, 'Предупреждений нет', 'No warnings'),
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              )
            else
              ..._warnings.map((row) => _warningTile(row, isRu)),
            const SizedBox(height: 12),
            if (_restrictionsLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: LinearProgressIndicator(),
              ),
            if (_restrictions.isEmpty)
              Text(
                _t(isRu, 'Ограничений нет', 'No restrictions'),
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              )
            else
              ..._restrictions.map((row) => _restrictionTile(row, isRu)),
          ],
        ),
      ],
    );
  }

  Widget _warningTile(Map<String, dynamic> row, bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    final status = row['status']?.toString() ?? '';
    final active = status == 'active';
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: active ? Colors.amber.withValues(alpha: 0.12) : Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            row['reason_title']?.toString() ?? _t(isRu, 'Предупреждение', 'Warning'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            row['reason_text']?.toString() ?? '-',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 4),
          Text(
            '${_t(isRu, 'Статус', 'Status')}: $status',
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink.withValues(alpha: 0.72),
            ),
          ),
        ],
      ),
    );
  }

  Widget _restrictionTile(Map<String, dynamic> row, bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    final active = row['is_active'] == true;
    final endsAt = row['ends_at']?.toString();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: active ? AppColors.accent.withValues(alpha: 0.08) : Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _restrictionLabel(isRu, row['restriction_type']?.toString() ?? ''),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            row['reason_description']?.toString() ?? '-',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 4),
          Text(
            active
                ? (endsAt == null ? _t(isRu, 'Активно бессрочно', 'Active permanently') : '${_t(isRu, 'Активно до', 'Active until')}: $endsAt')
                : _t(isRu, 'Неактивно', 'Inactive'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink.withValues(alpha: 0.72),
            ),
          ),
          if (active)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => _deactivateRestriction(row, isRu),
                child: Text(_t(isRu, 'Снять', 'Deactivate')),
              ),
            ),
        ],
      ),
    );
  }

  Widget _kv(String key, dynamic value) {
    final locale = AppLocaleScope.of(context).locale;
    final text = (value == null || value.toString().trim().isEmpty) ? '-' : value.toString();
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text('$key: $text', style: TextStyle(fontFamily: AppTypography.bodyFont(locale))),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(fontFamily: AppTypography.headerFont(locale), fontSize: 20)),
          const SizedBox(height: 8),
          ...children,
        ],
      ),
    );
  }
}
