import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'moderation_stats_screen.dart';
import 'moderation_user_screen.dart';
import 'moderation_users_search_screen.dart';
import 'login_screen.dart';

class ModerationQueueScreen extends StatefulWidget {
  const ModerationQueueScreen({super.key});

  static const route = '/moderation/queue';

  @override
  State<ModerationQueueScreen> createState() => _ModerationQueueScreenState();
}

class _ModerationQueueScreenState extends State<ModerationQueueScreen>
    with SingleTickerProviderStateMixin {
  final _api = ApiClient.defaultClient();

  late final TabController _tabController;

  bool _loading = true;
  String? _error;
  String _status = 'open';
  String _entityFilter = 'all';
  List<Map<String, dynamic>> _items = const [];
  List<Map<String, dynamic>> _reasons = const [];
  final Set<String> _busyIds = <String>{};

  String? get _token => AppSession.instance.accessToken;

  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  String _statusLabel(String value, bool isRu) {
    return switch (value) {
      'open' => isRu ? 'Открыто' : 'Open',
      'in_progress' => isRu ? 'В работе' : 'In progress',
      'done' => isRu ? 'Готово' : 'Done',
      _ => value,
    };
  }

  String _entityTypeLabel(String value, bool isRu) {
    return switch (value) {
      'new_post' => isRu ? 'Новый пост' : 'New post',
      'complaint' => isRu ? 'Жалоба' : 'Complaint',
      'message_report' => isRu ? 'Жалоба на сообщение' : 'Message report',
      'suspicious_case' => isRu ? 'Подозрительный случай' : 'Suspicious case',
      'verification' => isRu ? 'Верификация' : 'Verification',
      'appeal' => isRu ? 'Апелляция' : 'Appeal',
      _ => value,
    };
  }

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadQueue();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadQueue() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final query = {'status': _status, 'limit': '50', 'offset': '0'};
      if (_entityFilter != 'all') {
        query['entity_type'] = _entityFilter;
      }

      final res = await _api.getJson(
        '/moderation/queue',
        accessToken: _token,
        query: query,
      );
      final reasonsRes = _reasons.isEmpty
          ? await _api.getJson(
              '/moderation/reasons',
              accessToken: _token,
              query: const {'applies_to': 'moderation_reject'},
            )
          : null;
      if (!mounted) return;

      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }

      final data = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList();

      setState(() {
        _items = data;
        if (reasonsRes?.statusCode == 200) {
          _reasons = (jsonDecode(reasonsRes!.body) as List<dynamic>)
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

  Future<void> _take(String queueId) async {
    await _runQueueAction(
      queueId,
      () => _api.postJson(
        '/moderation/queue/$queueId/take',
        {},
        accessToken: _token,
      ),
    );
  }

  Future<void> _approve(Map<String, dynamic> item) async {
    final queueId = item['id'].toString();
    var favorite = false;
    if ((item['entity_type']?.toString() ?? '') == 'verification') {
      final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
      final shouldApprove = await showDialog<bool>(
        context: context,
        builder: (context) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: Text(
              _t(isRu, 'Одобрить верификацию', 'Approve verification'),
            ),
            content: SwitchListTile(
              value: favorite,
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(Icons.star, color: Colors.amber),
              onChanged: (value) => setDialogState(() => favorite = value),
              title: Text(
                _t(
                  isRu,
                  'Дать статус «Фаворит InkMatch»',
                  'Grant InkMatch favorite status',
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
                child: Text(_t(isRu, 'Одобрить', 'Approve')),
              ),
            ],
          ),
        ),
      );
      if (shouldApprove != true) return;
    }

    await _runQueueAction(
      queueId,
      () => _api.postJson('/moderation/queue/$queueId/approve', {
        'favorite': favorite,
      }, accessToken: _token),
    );
  }

  Future<void> _reject(String queueId) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final reasonCtrl = TextEditingController();
    String? reasonId;
    var blockAuthor = false;

    final shouldReject = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(
            _t(
              isRu,
              'Отклонить объект',
              'Reject item',
            ),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_reasons.isNotEmpty)
                DropdownButtonFormField<String>(
                  value: reasonId,
                  decoration: InputDecoration(
                    labelText: _t(isRu, 'Причина из справочника', 'Reason from catalog'),
                  ),
                  items: _reasons.map((row) {
                    return DropdownMenuItem<String>(
                      value: row['id']?.toString(),
                      child: Text(row['title']?.toString() ?? ''),
                    );
                  }).toList(),
                  onChanged: (value) => setDialogState(() => reasonId = value),
                ),
              if (_reasons.isNotEmpty) const SizedBox(height: 8),
              TextField(
                controller: reasonCtrl,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: _t(
                    isRu,
                    'Причина',
                    'Reason',
                  ),
                ),
              ),
              const SizedBox(height: 8),
              SwitchListTile(
                value: blockAuthor,
                contentPadding: EdgeInsets.zero,
                onChanged: (v) => setDialogState(() => blockAuthor = v),
                title: Text(
                  _t(
                    isRu,
                    'Заблокировать автора',
                    'Block author',
                  ),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(
                _t(isRu, 'Отмена', 'Cancel'),
              ),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.pop(context, true),
              child: Text(
                _t(
                  isRu,
                  'Отклонить',
                  'Reject',
                ),
              ),
            ),
          ],
        ),
      ),
    );

    if (shouldReject != true) return;

    await _runQueueAction(
      queueId,
      () => _api.postJson('/moderation/queue/$queueId/reject', {
        'reason': reasonCtrl.text.trim().isEmpty
            ? null
            : reasonCtrl.text.trim(),
        if (reasonId != null) 'reason_id': reasonId,
        'block_author': blockAuthor,
      }, accessToken: _token),
    );
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

  Future<void> _quickRestrictUser(String userId, bool isRu) async {
    var type = 'posting_disabled';
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
    if (ok != true) return;
    final reason = reasonCtrl.text.trim();
    if (reason.isEmpty) {
      _showError(_t(isRu, 'Укажите причину', 'Enter a reason'));
      return;
    }
    final duration = int.tryParse(durationCtrl.text.trim());
    final res = await _api.postJson(
      '/moderation/users/$userId/restrictions',
      {
        'restriction_type': type,
        'reason': reason,
        if (duration != null) 'duration_hours': duration,
      },
      accessToken: _token,
    );
    if (!mounted) return;
    if (res.statusCode == 201) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_t(isRu, 'Ограничение применено', 'Restriction applied'))),
      );
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  Future<void> _runQueueAction(
    String queueId,
    Future<dynamic> Function() request,
  ) async {
    if (_busyIds.contains(queueId)) return;
    setState(() => _busyIds.add(queueId));
    try {
      final res = await request();
      if (!mounted) return;
      if (res.statusCode == 200) {
        await _loadQueue();
      } else {
        _showError('${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      if (!mounted) return;
      _showError('$e');
    } finally {
      if (mounted) setState(() => _busyIds.remove(queueId));
    }
  }

  Future<void> _openEntityCard(String queueId) async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    try {
      final res = await _api.getJson(
        '/moderation/queue/$queueId',
        accessToken: _token,
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        _showError('${res.statusCode}: ${res.body}');
        return;
      }

      final payload = jsonDecode(res.body) as Map<String, dynamic>;
      final entityPayload =
          (payload['payload'] as Map<String, dynamic>? ?? <String, dynamic>{});
      final entries = entityPayload.entries.toList();
      final authorId = entityPayload['author_id']?.toString();
      final targetOwnerId = entityPayload['target_owner_user_id']?.toString();
      final masterId = entityPayload['master_id']?.toString();
      final appellantId = entityPayload['appellant_user_id']?.toString();
      final restrictUserId = targetOwnerId ?? authorId ?? masterId ?? appellantId;
      final isVerification =
          payload['entity_type']?.toString() == 'verification';

      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (context) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _t(
                      isRu,
                      'Карточка сущности',
                      'Entity card',
                    ),
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 24,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (isVerification)
                    _buildVerificationPayload(entityPayload, isRu, locale)
                  else
                    ...entries
                        .where((entry) => entry.key != 'target_preview' && entry.key != 'attachments')
                        .map(
                          (entry) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(
                              '${entry.key}: ${entry.value ?? '-'}',
                              style: TextStyle(
                                fontFamily: AppTypography.bodyFont(locale),
                              ),
                            ),
                          ),
                        ),
                  if (entityPayload['image_url'] != null &&
                      entityPayload['image_url'].toString().isNotEmpty) ...[
                    const SizedBox(height: 10),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        entityPayload['image_url'].toString(),
                        height: 220,
                        width: double.infinity,
                        fit: BoxFit.cover,
                      ),
                    ),
                  ],
                  if (entityPayload['target_preview']
                      is Map<String, dynamic>) ...[
                    const SizedBox(height: 10),
                    Builder(
                      builder: (_) {
                        final preview =
                            entityPayload['target_preview']
                                as Map<String, dynamic>;
                        final text = preview['text']?.toString();
                        final imageUrl =
                            preview['image_url']?.toString() ??
                            preview['attachment_url']?.toString();
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (text != null && text.isNotEmpty)
                              Text(
                                '${_t(isRu, 'Содержимое', 'Content')}: $text',
                                style: TextStyle(
                                  fontFamily: AppTypography.bodyFont(locale),
                                ),
                              ),
                            if (imageUrl != null && imageUrl.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(12),
                                child: Image.network(
                                  imageUrl,
                                  height: 220,
                                  width: double.infinity,
                                  fit: BoxFit.cover,
                                ),
                              ),
                            ],
                          ],
                        );
                      },
                    ),
                  ],
                  if (entityPayload['attachments'] is List<dynamic>) ...[
                    const SizedBox(height: 10),
                    Text(
                      _t(isRu, 'Вложения', 'Attachments'),
                      style: TextStyle(
                        fontFamily: AppTypography.bodyFont(locale),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    ...(entityPayload['attachments'] as List<dynamic>)
                        .whereType<Map<String, dynamic>>()
                        .map((attachment) {
                      final url = attachment['file_url']?.toString() ?? '';
                      final type = attachment['file_type']?.toString() ?? '';
                      return Align(
                        alignment: Alignment.centerLeft,
                        child: TextButton.icon(
                          onPressed: url.isEmpty ? null : () => _openUrl(url),
                          icon: const Icon(Icons.attach_file),
                          label: Text(type.isEmpty ? url : type),
                        ),
                      );
                    }),
                  ],
                  const SizedBox(height: 10),
                  if (restrictUserId != null && restrictUserId.isNotEmpty)
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: () async {
                          Navigator.pop(context);
                          await _quickRestrictUser(restrictUserId, isRu);
                        },
                        icon: const Icon(Icons.gpp_maybe_outlined),
                        label: Text(
                          _t(
                            isRu,
                            'Ограничить пользователя',
                            'Restrict user',
                          ),
                        ),
                      ),
                    ),
                  if (masterId != null && masterId.isNotEmpty)
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.person),
                        onPressed: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            this.context,
                            ModerationUserScreen.route,
                            arguments: ModerationUserScreenArgs(
                              userId: masterId,
                            ),
                          );
                        },
                        label: Text(
                          _t(
                            isRu,
                            'Открыть профиль мастера',
                            'Open master profile',
                          ),
                        ),
                      ),
                    ),
                  if (authorId != null && authorId.isNotEmpty)
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        onPressed: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            this.context,
                            ModerationUserScreen.route,
                            arguments: ModerationUserScreenArgs(
                              userId: authorId,
                            ),
                          );
                        },
                        child: Text(
                          _t(
                            isRu,
                            'Открыть автора',
                            'Open author',
                          ),
                        ),
                      ),
                    ),
                  if (targetOwnerId != null && targetOwnerId.isNotEmpty)
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        onPressed: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            this.context,
                            ModerationUserScreen.route,
                            arguments: ModerationUserScreenArgs(
                              userId: targetOwnerId,
                            ),
                          );
                        },
                        child: Text(
                          _t(
                            isRu,
                            'Открыть владельца цели',
                            'Open target owner',
                          ),
                        ),
                      ),
                    ),
                  if (appellantId != null && appellantId.isNotEmpty)
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        onPressed: () {
                          Navigator.pop(context);
                          Navigator.pushNamed(
                            this.context,
                            ModerationUserScreen.route,
                            arguments: ModerationUserScreenArgs(
                              userId: appellantId,
                            ),
                          );
                        },
                        child: Text(
                          _t(
                            isRu,
                            'Открыть автора апелляции',
                            'Open appellant',
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      );
    } catch (e) {
      _showError('$e');
    }
  }

  Widget _buildVerificationPayload(
    Map<String, dynamic> payload,
    bool isRu,
    Locale locale,
  ) {
    final personalData =
        payload['personal_data'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final documents = (payload['documents'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();

    Widget line(String label, Object? value) {
      final text = value?.toString();
      if (text == null || text.isEmpty || text == 'null') {
        return const SizedBox.shrink();
      }
      return Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(
          '$label: $text',
          style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        line('Request ID', payload['request_id']),
        line(_t(isRu, 'Статус', 'Status'), payload['status']),
        line(_t(isRu, 'Комментарий', 'Comment'), payload['comments']),
        line(
          _t(isRu, 'Причина отказа', 'Rejection reason'),
          payload['rejection_reason'],
        ),
        const SizedBox(height: 10),
        Text(
          _t(isRu, 'Личные данные', 'Personal data'),
          style: TextStyle(
            fontFamily: AppTypography.bodyFont(locale),
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        line(_t(isRu, 'Имя', 'First name'), personalData['first_name']),
        line(_t(isRu, 'Фамилия', 'Last name'), personalData['last_name']),
        line(_t(isRu, 'Отчество', 'Patronymic'), personalData['patronymic']),
        line(
          _t(isRu, 'Дата рождения', 'Birth date'),
          personalData['birth_date'],
        ),
        line(
          _t(isRu, 'Гражданство', 'Citizenship'),
          personalData['citizenship'],
        ),
        const SizedBox(height: 12),
        Text(
          _t(isRu, 'Файлы', 'Files'),
          style: TextStyle(
            fontFamily: AppTypography.bodyFont(locale),
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        if (documents.isEmpty)
          Text(_t(isRu, 'Файлы не прикреплены', 'No attached files')),
        ...documents.map(
          (document) => _VerificationDocumentTile(
            document: document,
            isRu: isRu,
            locale: locale,
            openUrl: _openUrl,
          ),
        ),
      ],
    );
  }

  Future<void> _openUrl(String rawUrl) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final uri = Uri.tryParse(rawUrl);
    if (uri == null) {
      _showError(isRu ? 'Некорректная ссылка' : 'Invalid URL');
      return;
    }
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok) {
      _showError(isRu ? 'Не удалось открыть файл' : 'Could not open file');
    }
  }

  Future<void> _openUserByIdDialog() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final ctrl = TextEditingController();
    final userId = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          _t(
            isRu,
            'Открыть пользователя',
            'Open user',
          ),
        ),
        content: TextField(
          controller: ctrl,
          decoration: InputDecoration(
            labelText: isRu ? 'ID пользователя (UUID)' : 'User ID (UUID)',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              _t(isRu, 'Отмена', 'Cancel'),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, ctrl.text.trim()),
            child: Text(
              _t(isRu, 'Открыть', 'Open'),
            ),
          ),
        ],
      ),
    );

    if (userId == null || userId.isEmpty || !mounted) return;
    Navigator.pushNamed(
      context,
      ModerationUserScreen.route,
      arguments: ModerationUserScreenArgs(userId: userId),
    );
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(
          _t(
            isRu,
            'Модерация',
            'Moderation',
          ),
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(
              text: _t(
                isRu,
                'Очередь',
                'Queue',
              ),
            ),
            Tab(
              text: _t(
                isRu,
                'Объекты',
                'Objects',
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            onPressed: () =>
                Navigator.pushNamed(context, ModerationUsersSearchScreen.route),
            icon: const Icon(Icons.person_search),
          ),
          IconButton(
            onPressed: () =>
                Navigator.pushNamed(context, ModerationStatsScreen.route),
            icon: const Icon(Icons.bar_chart),
          ),
          IconButton(
            onPressed: () {
              AppSession.instance.clear();
              Navigator.pushNamedAndRemoveUntil(
                context,
                LoginScreen.route,
                (route) => false,
              );
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: SegmentedButton<String>(
              segments: <ButtonSegment<String>>[
                ButtonSegment(
                  value: 'open',
                  label: Text(
                    _t(
                      isRu,
                      'Открытые',
                      'Open',
                    ),
                  ),
                ),
                ButtonSegment(
                  value: 'in_progress',
                  label: Text(
                    _t(
                      isRu,
                      'В работе',
                      'In progress',
                    ),
                  ),
                ),
                ButtonSegment(
                  value: 'done',
                  label: Text(
                    _t(isRu, 'Готово', 'Done'),
                  ),
                ),
              ],
              selected: <String>{_status},
              onSelectionChanged: (selection) {
                final next = selection.first;
                if (next == _status) return;
                setState(() => _status = next);
                _loadQueue();
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Wrap(
              spacing: 8,
              children: [
                _entityChip(_t(isRu, 'Все', 'All'), 'all'),
                _entityChip(
                  _t(
                    isRu,
                    'Жалобы',
                    'Complaints',
                  ),
                  'complaint',
                ),
                _entityChip(
                  _t(isRu, 'Жалобы на сообщения', 'Message reports'),
                  'message_report',
                ),
                _entityChip(
                  _t(isRu, 'Подозрительные', 'Suspicious'),
                  'suspicious_case',
                ),
                _entityChip(
                  _t(
                    isRu,
                    'Новые посты',
                    'New posts',
                  ),
                  'new_post',
                ),
                _entityChip(
                  _t(isRu, 'Верификация', 'Verification'),
                  'verification',
                ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _loadQueue,
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildListView(isRu, locale, false),
                  _buildListView(isRu, locale, true),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _entityChip(String label, String value) {
    final selected = _entityFilter == value;
    return ChoiceChip(
      showCheckmark: false,
      selected: selected,
      selectedColor: AppColors.accent,
      labelStyle: TextStyle(color: selected ? Colors.white : AppColors.ink),
      label: Text(label),
      onSelected: (_) {
        setState(() => _entityFilter = value);
        _loadQueue();
      },
    );
  }

  Widget _buildListView(bool isRu, Locale locale, bool objectsTab) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(_error!),
          const SizedBox(height: 8),
          ElevatedButton(
            onPressed: _loadQueue,
            child: Text(
              _t(
                isRu,
                'Повторить',
                'Retry',
              ),
            ),
          ),
        ],
      );
    }
    if (_items.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            _t(
              isRu,
              'Очередь пуста',
              'Queue is empty',
            ),
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontSize: 16,
            ),
          ),
        ],
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
      itemCount: _items.length,
      separatorBuilder: (_, index) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final item = _items[index];
        final queueId = item['id'].toString();
        final busy = _busyIds.contains(queueId);

        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.ink.withValues(alpha: 0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item['entity_title']?.toString() ??
                    _t(
                      isRu,
                      'Без названия',
                      'Untitled',
                    ),
                style: TextStyle(
                  fontFamily: AppTypography.bodyFont(locale),
                  fontWeight: FontWeight.w700,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                item['entity_subtitle']?.toString() ?? '',
                style: TextStyle(
                  fontFamily: AppTypography.bodyFont(locale),
                  color: AppColors.ink.withValues(alpha: 0.75),
                ),
              ),
              const SizedBox(height: 8),
              if (!objectsTab)
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _chip('ID: ${queueId.substring(0, 8)}'),
                    _chip(
                      '${_t(isRu, 'Тип', 'Type')}: ${_entityTypeLabel(item['entity_type']?.toString() ?? '', isRu)}',
                    ),
                    _chip(
                      '${_t(isRu, 'Статус', 'Status')}: ${_statusLabel(item['status']?.toString() ?? '', isRu)}',
                    ),
                    _chip(
                      '${_t(isRu, 'Приоритет', 'Priority')}: ${item['priority']}',
                    ),
                  ],
                )
              else
                Text(
                  '${_t(isRu, 'Объект', 'Entity')} ${item['entity_id']}',
                  style: TextStyle(
                    fontFamily: AppTypography.bodyFont(locale),
                    color: AppColors.ink.withValues(alpha: 0.85),
                    fontSize: 12,
                  ),
                ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if ((item['status']?.toString() ?? '') == 'open')
                    OutlinedButton(
                      onPressed: busy ? null : () => _take(queueId),
                      child: Text(
                        _t(isRu, 'Взять', 'Take'),
                      ),
                    ),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.shade700,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: busy ? null : () => _approve(item),
                    child: Text(
                      _t(
                        isRu,
                        'Одобрить',
                        'Approve',
                      ),
                    ),
                  ),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accent,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: busy ? null : () => _reject(queueId),
                    child: Text(
                      _t(
                        isRu,
                        'Отклонить',
                        'Reject',
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: () => _openEntityCard(queueId),
                    child: Text(
                      _t(
                        isRu,
                        'Карточка',
                        'Card',
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _chip(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.ink.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label, style: const TextStyle(fontSize: 12)),
    );
  }
}

class _VerificationDocumentTile extends StatelessWidget {
  const _VerificationDocumentTile({
    required this.document,
    required this.isRu,
    required this.locale,
    required this.openUrl,
  });

  final Map<String, dynamic> document;
  final bool isRu;
  final Locale locale;
  final Future<void> Function(String url) openUrl;

  bool get _isImage {
    final fileType = document['file_type']?.toString().toLowerCase() ?? '';
    final url = document['file_url']?.toString().toLowerCase() ?? '';
    return fileType.startsWith('image/') ||
        url.endsWith('.jpg') ||
        url.endsWith('.jpeg') ||
        url.endsWith('.png') ||
        url.endsWith('.webp');
  }

  @override
  Widget build(BuildContext context) {
    final url = document['file_url']?.toString() ?? '';
    final title = document['title']?.toString();
    final issuer = document['issuer']?.toString();
    final issuedDate = document['issued_date']?.toString();

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.16)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _isImage ? Icons.image : Icons.picture_as_pdf,
                color: _isImage ? AppColors.ink : Colors.red.shade700,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title?.isNotEmpty == true
                      ? title!
                      : (document['document_type']?.toString() ?? 'document'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontFamily: AppTypography.bodyFont(locale),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          if (issuer != null && issuer.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '${isRu ? 'Кем выдано' : 'Issuer'}: $issuer',
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              ),
            ),
          if (issuedDate != null && issuedDate.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '${isRu ? 'Дата' : 'Date'}: $issuedDate',
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              ),
            ),
          if (_isImage && url.isNotEmpty) ...[
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.network(
                url,
                height: 180,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => Container(
                  height: 80,
                  alignment: Alignment.center,
                  color: AppColors.ink.withValues(alpha: 0.08),
                  child: Text(
                    isRu ? 'Не удалось загрузить превью' : 'Preview failed',
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: url.isEmpty ? null : () => openUrl(url),
              icon: const Icon(Icons.open_in_new),
              label: Text(isRu ? 'Открыть файл' : 'Open file'),
            ),
          ),
        ],
      ),
    );
  }
}
