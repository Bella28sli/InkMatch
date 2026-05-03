import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class RestrictionHistoryScreen extends StatefulWidget {
  const RestrictionHistoryScreen({super.key});

  static const route = '/account/restrictions';

  @override
  State<RestrictionHistoryScreen> createState() =>
      _RestrictionHistoryScreenState();
}

class _RestrictionHistoryScreenState extends State<RestrictionHistoryScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _warnings = [];

  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) {
      setState(() {
        _loading = false;
        _error = 'No token';
      });
      return;
    }
    try {
      final res = await _api.getJson('/account/restrictions', accessToken: token);
      final warningsRes = await _api.getJson('/account/warnings', accessToken: token);
      if (!mounted) return;
      if (res.statusCode == 200) {
        setState(() {
          _items = (jsonDecode(res.body) as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          if (warningsRes.statusCode == 200) {
            _warnings = (jsonDecode(warningsRes.body) as List)
                .map((e) => Map<String, dynamic>.from(e as Map))
                .toList();
          }
          _loading = false;
        });
      } else {
        setState(() {
          _error = '${res.statusCode}: ${res.body}';
          _loading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
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

  Future<void> _createAppeal(Map<String, dynamic> row, bool isRu) async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;
    final ctrl = TextEditingController();
    final selectedFiles = <PlatformFile>[];

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(_t(isRu, 'Подать апелляцию', 'Create appeal')),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: ctrl,
                  minLines: 3,
                  maxLines: 6,
                  decoration: InputDecoration(
                    labelText: _t(
                      isRu,
                      'Почему ограничение нужно пересмотреть',
                      'Why this should be reviewed',
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      final result = await FilePicker.platform.pickFiles(
                        allowMultiple: true,
                        withData: false,
                        type: FileType.custom,
                        allowedExtensions: const [
                          'jpg',
                          'jpeg',
                          'png',
                          'webp',
                          'heic',
                          'pdf',
                          'doc',
                          'docx',
                          'txt',
                        ],
                      );
                      if (result == null) return;
                      setDialogState(() {
                        selectedFiles
                          ..clear()
                          ..addAll(
                            result.files.where((file) => file.path != null),
                          );
                      });
                    },
                    icon: const Icon(Icons.attach_file),
                    label: Text(_t(isRu, 'Прикрепить документы', 'Attach files')),
                  ),
                ),
                if (selectedFiles.isNotEmpty)
                  Flexible(
                    child: ListView.builder(
                      shrinkWrap: true,
                      itemCount: selectedFiles.length,
                      itemBuilder: (context, index) {
                        final file = selectedFiles[index];
                        return ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.insert_drive_file_outlined),
                          title: Text(
                            file.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text('${(file.size / 1024).ceil()} KB'),
                          trailing: IconButton(
                            icon: const Icon(Icons.close),
                            onPressed: () => setDialogState(() {
                              selectedFiles.removeAt(index);
                            }),
                          ),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(_t(isRu, 'Отмена', 'Cancel')),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(_t(isRu, 'Отправить', 'Send')),
            ),
          ],
        ),
      ),
    );
    if (ok != true || !mounted) return;

    final description = ctrl.text.trim();
    if (description.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_t(isRu, 'Опишите причину апелляции', 'Enter appeal reason')),
        ),
      );
      return;
    }

    final res = await _api.postJson(
      '/appeals',
      {
        'target_type': 'user_restriction',
        'target_id': row['id'],
        'description': description,
        'reason_text': description,
      },
      accessToken: token,
    );
    if (!mounted) return;

    var uploaded = 0;
    if (res.statusCode == 201 && selectedFiles.isNotEmpty) {
      final payload = jsonDecode(res.body) as Map<String, dynamic>;
      final appealId = payload['id']?.toString();
      if (appealId != null && appealId.isNotEmpty) {
        for (final item in selectedFiles) {
          final path = item.path;
          if (path == null) continue;
          final uploadRes = await _api.postMultipart(
            '/appeals/$appealId/attachments',
            file: File(path),
            fieldName: 'file',
            accessToken: token,
          );
          if (uploadRes.statusCode == 201) uploaded++;
        }
      }
    }
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          res.statusCode == 201
              ? selectedFiles.isEmpty
                  ? _t(isRu, 'Апелляция отправлена', 'Appeal sent')
                  : _t(
                      isRu,
                      'Апелляция отправлена, файлов загружено: $uploaded',
                      'Appeal sent, files uploaded: $uploaded',
                    )
              : '${res.statusCode}: ${res.body}',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    return Scaffold(
      appBar: AppBar(
        title: Text(
          _t(isRu, 'История ограничений', 'Restriction history'),
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _items.isEmpty && _warnings.isEmpty
                  ? Center(
                      child: Text(_t(isRu, 'Ограничений нет', 'No restrictions')),
                    )
                  : _buildHistoryList(locale, isRu),
    );
  }

  Widget _buildHistoryList(Locale locale, bool isRu) {
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        if (_warnings.isNotEmpty) ...[
          Text(
            _t(isRu, 'Предупреждения', 'Warnings'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          ..._warnings.map((row) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _WarningCard(row: row, isRu: isRu),
              )),
          const SizedBox(height: 8),
        ],
        if (_items.isNotEmpty) ...[
          Text(
            _t(isRu, 'Ограничения', 'Restrictions'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          ..._items.map((row) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _RestrictionCard(
                  row: row,
                  label: _restrictionLabel(
                    isRu,
                    row['restriction_type']?.toString() ?? '',
                  ),
                  isRu: isRu,
                  onAppeal: () => _createAppeal(row, isRu),
                ),
              )),
        ],
      ],
    );
  }
}

class _WarningCard extends StatelessWidget {
  const _WarningCard({required this.row, required this.isRu});

  final Map<String, dynamic> row;
  final bool isRu;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final status = row['status']?.toString() ?? '';
    final active = status == 'active';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: active ? Colors.amber.withValues(alpha: 0.12) : Colors.white.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            row['reason_title']?.toString() ?? (isRu ? 'Предупреждение' : 'Warning'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
              color: AppColors.ink,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            row['reason_text']?.toString() ?? '-',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 6),
          Text(
            '${isRu ? 'Статус' : 'Status'}: $status',
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink.withValues(alpha: 0.72),
            ),
          ),
        ],
      ),
    );
  }
}

class _RestrictionCard extends StatelessWidget {
  const _RestrictionCard({
    required this.row,
    required this.label,
    required this.isRu,
    required this.onAppeal,
  });

  final Map<String, dynamic> row;
  final String label;
  final bool isRu;
  final VoidCallback onAppeal;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final active = row['is_active'] == true;
    final endsAt = row['ends_at']?.toString();
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              fontWeight: FontWeight.w700,
              color: AppColors.ink,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            row['reason_description']?.toString() ?? '-',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 6),
          Text(
            active
                ? (endsAt == null
                    ? (isRu ? 'Активно бессрочно' : 'Active permanently')
                    : '${isRu ? 'Активно до' : 'Active until'}: $endsAt')
                : (isRu ? 'Неактивно' : 'Inactive'),
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink.withValues(alpha: 0.72),
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: onAppeal,
            icon: const Icon(Icons.rate_review_outlined),
            label: Text(isRu ? 'Подать апелляцию' : 'Appeal'),
          ),
        ],
      ),
    );
  }
}
