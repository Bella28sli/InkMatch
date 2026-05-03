import 'dart:convert';
import 'dart:io';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class ModerationStatsScreen extends StatefulWidget {
  const ModerationStatsScreen({super.key});

  static const route = '/moderation/stats';

  @override
  State<ModerationStatsScreen> createState() => _ModerationStatsScreenState();
}

class _ModerationStatsScreenState extends State<ModerationStatsScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _stats;

  DateTime? _dateFrom;
  DateTime? _dateTo;

  String? get _token => AppSession.instance.accessToken;
  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  static const Map<String, String> _ruLabels = {
    'queue_open': 'Очередь: открыто',
    'queue_in_progress': 'Очередь: в работе',
    'queue_done': 'Очередь: закрыто',
    'queue_complaints_open': 'Жалобы в очереди',
    'queue_new_posts_open': 'Новые посты в очереди',
    'complaints_open': 'Жалобы: открыто',
    'complaints_in_review': 'Жалобы: на проверке',
    'complaints_resolved': 'Жалобы: решено',
    'complaints_rejected': 'Жалобы: отклонено',
    'active_restrictions': 'Активные ограничения',
    'actions_total': 'Всего действий модерации',
    'posts_created': 'Создано постов',
    'users_registered': 'Новых пользователей',
    'chats_created': 'Создано чатов',
    'messages_sent': 'Отправлено сообщений',
    'collections_created': 'Создано коллекций',
    'comments_created': 'Создано комментариев',
    'reviews_created': 'Создано отзывов',
    'avg_queue_priority': 'Средний приоритет очереди',
    'avg_resolution_minutes': 'Среднее время решения (мин)',
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await _api.getJson('/moderation/stats', accessToken: _token, query: _statsQuery());
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }
      setState(() {
        _stats = jsonDecode(res.body) as Map<String, dynamic>;
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

  Map<String, String> _statsQuery() {
    final query = <String, String>{};
    if (_dateFrom != null) query['date_from'] = _dateFrom!.toIso8601String();
    if (_dateTo != null) query['date_to'] = _dateTo!.toIso8601String();
    return query;
  }

  Future<void> _pickDateTime({required bool isFrom}) async {
    final locale = AppLocaleScope.of(context).locale;
    final now = DateTime.now();
    final initial = isFrom ? (_dateFrom ?? now.subtract(const Duration(days: 7))) : (_dateTo ?? now);

    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
      locale: locale,
    );
    if (date == null || !mounted) return;

    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (!mounted) return;

    final picked = DateTime(date.year, date.month, date.day, time?.hour ?? 0, time?.minute ?? 0);
    setState(() {
      if (isFrom) {
        _dateFrom = picked;
      } else {
        _dateTo = picked;
      }
    });
    await _load();
  }

  Future<void> _export(String format) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    try {
      final path = format == 'csv' ? '/moderation/stats/export.csv' : '/moderation/stats/export.xlsx';
      final res = await _api.getJson(path, accessToken: _token, query: _statsQuery());
      if (!mounted) return;
      if (res.statusCode != 200) {
        _show('${res.statusCode}: ${res.body}');
        return;
      }

      final dir = await getApplicationDocumentsDirectory();
      final stamp = DateTime.now().millisecondsSinceEpoch;
      final file = File('${dir.path}/moderation_stats_$stamp.$format');
      await file.writeAsBytes(res.bodyBytes, flush: true);
      if (!mounted) return;
      _show(_t(isRu, 'Файл сохранен: ${file.path}', 'File saved: ${file.path}'));
    } catch (e) {
      if (!mounted) return;
      _show('$e');
    }
  }

  void _show(String text) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  String _formatDt(DateTime? dt) {
    if (dt == null) return '-';
    final mm = dt.month.toString().padLeft(2, '0');
    final dd = dt.day.toString().padLeft(2, '0');
    final hh = dt.hour.toString().padLeft(2, '0');
    final mi = dt.minute.toString().padLeft(2, '0');
    return '${dt.year}-$mm-$dd $hh:$mi';
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(_t(isRu, 'Статистика модерации', 'Moderation stats'), style: TextStyle(fontFamily: AppTypography.headerFont(locale))),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
                    children: [
                      _datePanel(isRu, locale),
                      const SizedBox(height: 10),
                      _exportPanel(isRu),
                      const SizedBox(height: 10),
                      _queuePie(isRu),
                      const SizedBox(height: 10),
                      _activityLine(isRu, locale),
                      const SizedBox(height: 10),
                      _moderatorProductivity(isRu, locale),
                      const SizedBox(height: 10),
                      ..._statsEntries(isRu, locale),
                    ],
                  ),
                ),
    );
  }

  Widget _datePanel(bool isRu, Locale locale) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.ink.withValues(alpha: 0.15))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(_t(isRu, 'Период', 'Date range'), style: TextStyle(fontFamily: AppTypography.headerFont(locale), fontSize: 20)),
        const SizedBox(height: 8),
        Text('${_t(isRu, 'С', 'From')}: ${_formatDt(_dateFrom)}', style: TextStyle(fontFamily: AppTypography.bodyFont(locale))),
        Text('${_t(isRu, 'По', 'To')}: ${_formatDt(_dateTo)}', style: TextStyle(fontFamily: AppTypography.bodyFont(locale))),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          OutlinedButton(onPressed: () => _pickDateTime(isFrom: true), child: Text(_t(isRu, 'Выбрать дату с', 'Pick FROM'))),
          OutlinedButton(onPressed: () => _pickDateTime(isFrom: false), child: Text(_t(isRu, 'Выбрать дату по', 'Pick TO'))),
          TextButton(
            onPressed: () {
              setState(() {
                _dateFrom = null;
                _dateTo = null;
              });
              _load();
            },
            child: Text(_t(isRu, 'Сбросить', 'Reset')),
          ),
        ]),
      ]),
    );
  }

  Widget _exportPanel(bool isRu) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        ElevatedButton.icon(onPressed: () => _export('csv'), icon: const Icon(Icons.download), label: Text(_t(isRu, 'Экспорт CSV', 'Export CSV'))),
        ElevatedButton.icon(onPressed: () => _export('xlsx'), icon: const Icon(Icons.table_chart), label: Text(_t(isRu, 'Экспорт Excel', 'Export Excel'))),
      ],
    );
  }

  Widget _queuePie(bool isRu) {
    final open = (_stats?['queue_open'] as num? ?? 0).toDouble();
    final inProgress = (_stats?['queue_in_progress'] as num? ?? 0).toDouble();
    final done = (_stats?['queue_done'] as num? ?? 0).toDouble();
    final total = open + inProgress + done;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.ink.withValues(alpha: 0.15))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(_t(isRu, 'Распределение очереди', 'Queue distribution'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        SizedBox(
          height: 180,
          child: total == 0
              ? Center(child: Text(_t(isRu, 'Нет данных', 'No data')))
              : PieChart(
                  PieChartData(
                    centerSpaceRadius: 36,
                    sectionsSpace: 2,
                    sections: [
                      PieChartSectionData(value: open, color: Colors.orange, title: open.toInt().toString()),
                      PieChartSectionData(value: inProgress, color: Colors.blue, title: inProgress.toInt().toString()),
                      PieChartSectionData(value: done, color: Colors.green, title: done.toInt().toString()),
                    ],
                  ),
                ),
        ),
        const SizedBox(height: 8),
        _legendRow(Colors.orange, _t(isRu, 'Открыто', 'Open')),
        _legendRow(Colors.blue, _t(isRu, 'В работе', 'In progress')),
        _legendRow(Colors.green, _t(isRu, 'Закрыто', 'Done')),
      ]),
    );
  }

  Widget _activityLine(bool isRu, Locale locale) {
    final trends = (_stats?['trends'] as List<dynamic>? ?? const []);
    final messageSpots = <FlSpot>[];
    final commentSpots = <FlSpot>[];
    final complaintSpots = <FlSpot>[];

    for (var i = 0; i < trends.length; i++) {
      final row = trends[i] as Map<String, dynamic>;
      messageSpots.add(FlSpot(i.toDouble(), ((row['messages'] as num?) ?? 0).toDouble()));
      commentSpots.add(FlSpot(i.toDouble(), ((row['comments'] as num?) ?? 0).toDouble()));
      complaintSpots.add(FlSpot(i.toDouble(), ((row['complaints'] as num?) ?? 0).toDouble()));
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.ink.withValues(alpha: 0.15))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(_t(isRu, 'Популярность по датам', 'Popularity by date'), style: TextStyle(fontFamily: AppTypography.headerFont(locale), fontSize: 18)),
        const SizedBox(height: 8),
        SizedBox(
          height: 220,
          child: trends.isEmpty
              ? Center(child: Text(_t(isRu, 'Нет данных', 'No data')))
              : LineChart(
                  LineChartData(
                    gridData: const FlGridData(show: true),
                    borderData: FlBorderData(show: true),
                    titlesData: const FlTitlesData(show: true),
                    lineBarsData: [
                      LineChartBarData(spots: messageSpots, color: Colors.blue, isCurved: true, dotData: const FlDotData(show: false)),
                      LineChartBarData(spots: commentSpots, color: Colors.green, isCurved: true, dotData: const FlDotData(show: false)),
                      LineChartBarData(spots: complaintSpots, color: Colors.red, isCurved: true, dotData: const FlDotData(show: false)),
                    ],
                  ),
                ),
        ),
        const SizedBox(height: 8),
        _legendRow(Colors.blue, _t(isRu, 'Синяя линия - сообщения', 'Blue line - messages')),
        _legendRow(Colors.green, _t(isRu, 'Зеленая линия - комментарии', 'Green line - comments')),
        _legendRow(Colors.red, _t(isRu, 'Красная линия - жалобы', 'Red line - complaints')),
      ]),
    );
  }

  List<Widget> _statsEntries(bool isRu, Locale locale) {
    final stats = _stats ?? const <String, dynamic>{};
    final entries = stats.entries
        .where((e) => e.key != 'trends' && e.key != 'moderator_productivity')
        .map((e) => _StatsTile(title: _ruLabels[e.key] ?? e.key, value: '${e.value}', locale: locale))
        .toList();
    return entries;
  }

  Widget _moderatorProductivity(bool isRu, Locale locale) {
    final rows = (_stats?['moderator_productivity'] as List<dynamic>? ?? const []);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _t(isRu, 'Продуктивность модераторов', 'Moderator productivity'),
            style: TextStyle(fontFamily: AppTypography.headerFont(locale), fontSize: 18),
          ),
          const SizedBox(height: 8),
          if (rows.isEmpty)
            Text(_t(isRu, 'Нет данных', 'No data'))
          else
            ...rows.map((raw) {
              final row = raw as Map<String, dynamic>;
              final name = row['nickname']?.toString().isNotEmpty == true
                  ? row['nickname'].toString()
                  : row['moderator_id'].toString();
              final line = isRu
                  ? 'взято: ${row['taken_count']} • решено: ${row['resolved_count']} • одобрено: ${row['approved_count']} • отклонено: ${row['rejected_count']} • ср. ${row['avg_resolution_minutes']} мин • просрочек: ${row['overdue_count']}'
                  : 'taken: ${row['taken_count']} • resolved: ${row['resolved_count']} • approved: ${row['approved_count']} • rejected: ${row['rejected_count']} • avg ${row['avg_resolution_minutes']} min • overdue: ${row['overdue_count']}';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: TextStyle(fontFamily: AppTypography.bodyFont(locale), fontWeight: FontWeight.w700)),
                    Text(line, style: TextStyle(fontFamily: AppTypography.bodyFont(locale), fontSize: 12)),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget _legendRow(Color color, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(99))),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _StatsTile extends StatelessWidget {
  const _StatsTile({required this.title, required this.value, required this.locale});

  final String title;
  final String value;
  final Locale locale;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.ink.withValues(alpha: 0.15))),
      child: Row(
        children: [
          Expanded(child: Text(title, style: TextStyle(fontFamily: AppTypography.bodyFont(locale)))),
          Text(value, style: TextStyle(fontFamily: AppTypography.headerFont(locale), fontSize: 16, color: AppColors.ink)),
        ],
      ),
    );
  }
}
