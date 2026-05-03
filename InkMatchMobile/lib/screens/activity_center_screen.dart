import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

enum ActivityRange { week, month, quarter }

class ActivityCenterScreen extends StatefulWidget {
  const ActivityCenterScreen({super.key});

  static const route = '/activity-center';

  @override
  State<ActivityCenterScreen> createState() => _ActivityCenterScreenState();
}

class _ActivityCenterScreenState extends State<ActivityCenterScreen> {
  final _api = ApiClient.defaultClient();
  ActivityRange _range = ActivityRange.month;

  bool _loading = true;
  String? _error;
  _StatsData? _data;

  String get _token => AppSession.instance.accessToken ?? '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  int get _rangeDays => switch (_range) {
    ActivityRange.week => 7,
    ActivityRange.month => 30,
    ActivityRange.quarter => 90,
  };

  Future<void> _load() async {
    if (_token.isEmpty) {
      setState(() {
        _loading = false;
        _error = AppLocaleScope.of(context).locale.languageCode == 'ru'
            ? 'Нужна авторизация'
            : 'Not authenticated';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await _api.getJson(
        '/account/activity-stats',
        accessToken: _token,
        query: {'range_days': _rangeDays.toString()},
      );

      if (!mounted) {
        return;
      }

      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Не удалось загрузить статистику активности'
                : 'Failed to load activity stats',
          );
        });
        return;
      }

      final raw = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _data = _StatsData.fromJson(raw);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  void _setRange(ActivityRange range) {
    if (_range == range) {
      return;
    }
    setState(() {
      _range = range;
    });
    _load();
  }

  Future<void> _shareSummary() async {
    final data = _data;
    if (data == null) {
      return;
    }

    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final text = isRu
        ? 'InkMatch статистика за ${data.days} дн: '
              'время ${data.timeMinutes} мин, '
              'сессий ${data.sessions}, '
              'активных дней ${data.activeDays}'
        : 'InkMatch stats for ${data.days}d: '
              'time ${data.timeMinutes} min, '
              'sessions ${data.sessions}, '
              'active days ${data.activeDays}';

    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          isRu
              ? 'Сводка скопирована. Можно поделиться.'
              : 'Summary copied. You can share it.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.ink,
        title: Text(
          isRu ? 'Центр активности' : 'Activity center',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
        actions: [
          IconButton(
            onPressed: _shareSummary,
            icon: const Icon(Icons.share_outlined),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
                ),
              ),
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(14),
                children: [
                  _rangeSelector(isRu, locale),
                  const SizedBox(height: 10),
                  _card(
                    locale,
                    isRu ? 'Ваши вкусы (сохранения)' : 'Your tastes (saves)',
                    Column(
                      children: [
                        _donutSection(
                          locale,
                          isRu ? 'Стили' : 'Styles',
                          _data!.styleShare,
                        ),
                        const SizedBox(height: 10),
                        _donutSection(
                          locale,
                          isRu ? 'Теги' : 'Tags',
                          _data!.tagShare,
                        ),
                      ],
                    ),
                  ),
                  _card(
                    locale,
                    isRu ? 'Время в приложении' : 'Time in app',
                    _metricsRow(locale, [
                      _MetricItem(
                        title: isRu ? 'Всего минут' : 'Total minutes',
                        value: _data!.timeMinutes.toString(),
                      ),
                      _MetricItem(
                        title: isRu ? 'Сессии' : 'Sessions',
                        value: _data!.sessions.toString(),
                      ),
                      _MetricItem(
                        title: isRu ? 'Активных дней' : 'Active days',
                        value: _data!.activeDays.toString(),
                      ),
                    ]),
                  ),
                  _card(
                    locale,
                    isRu ? 'Популярность' : 'Popularity',
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          height: 190,
                          child: CustomPaint(
                            painter: _LineChartPainter(_data!.popularity),
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 12,
                          runSpacing: 6,
                          children: [
                            _legendDot(const Color(0xFFFF1B43), isRu ? 'Лайки' : 'Likes'),
                            _legendDot(const Color(0xFF1F1F1F), isRu ? 'Просмотры' : 'Views'),
                            _legendDot(const Color(0xFF7A7A7A), isRu ? 'Комментарии' : 'Comments'),
                          ],
                        ),
                      ],
                    ),
                  ),
                  _card(
                    locale,
                    isRu ? 'Дополнительно' : 'Additional insights',
                    _metricsRow(
                      locale,
                      _data!.extra.entries
                          .map(
                            (e) => _MetricItem(
                              title: _metricLabel(e.key, isRu),
                              value: _metricValue(e.key, e.value),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  String _metricLabel(String key, bool isRu) {
    switch (key) {
      case 'save_to_inkmatch_rate':
        return 'Save -> InkMatch';
      case 'streak_days':
        return isRu ? 'Серия дней' : 'Streak days';
      case 'offers_sent':
        return isRu ? 'Офферов отправлено' : 'Offers sent';
      case 'avg_offer_price':
        return isRu ? 'Средний оффер' : 'Avg offer';
      case 'matches_count':
        return isRu ? 'Матчей' : 'Matches';
      case 'collections_created':
        return isRu ? 'Коллекций создано' : 'Collections created';
      case 'likes_given':
        return isRu ? 'Лайков поставлено' : 'Likes given';
      case 'comments_written':
        return isRu ? 'Комментариев написано' : 'Comments written';
      default:
        return key;
    }
  }

  String _metricValue(String key, double value) {
    if (key == 'save_to_inkmatch_rate') {
      return '${(value * 100).toStringAsFixed(1)}%';
    }
    if (value == value.roundToDouble()) {
      return value.toInt().toString();
    }
    return value.toStringAsFixed(2);
  }

  Widget _rangeSelector(bool isRu, Locale locale) {
    return Row(
      children: [
        _rangeChip(locale, isRu ? '7 дней' : '7 days', ActivityRange.week),
        const SizedBox(width: 8),
        _rangeChip(locale, isRu ? '30 дней' : '30 days', ActivityRange.month),
        const SizedBox(width: 8),
        _rangeChip(locale, isRu ? '90 дней' : '90 days', ActivityRange.quarter),
      ],
    );
  }

  Widget _rangeChip(Locale locale, String label, ActivityRange value) {
    final active = _range == value;
    return ChoiceChip(
      selected: active,
      label: Text(
        label,
        style: TextStyle(
          fontFamily: AppTypography.bodyFont(locale),
          color: active ? Colors.white : AppColors.ink,
        ),
      ),
      selectedColor: AppColors.accent,
      onSelected: (_) => _setRange(value),
    );
  }

  Widget _card(Locale locale, String title, Widget child) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withValues(alpha: 0.14)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 20,
              color: AppColors.ink,
            ),
          ),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }

  Widget _donutSection(Locale locale, String title, List<_SliceData> values) {
    return Row(
      children: [
        SizedBox(
          width: 92,
          height: 92,
          child: CustomPaint(painter: _DonutPainter(values)),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontFamily: AppTypography.bodyFont(locale),
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              if (values.isEmpty)
                Text(
                  'No data',
                  style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
                )
              else
                ...values.map(
                  (e) => Text(
                    '${e.label}: ${e.sharePercent.toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _metricsRow(Locale locale, List<_MetricItem> items) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: items
          .map(
            (item) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.ink,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.value,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }
}

class _MetricItem {
  const _MetricItem({required this.title, required this.value});

  final String title;
  final String value;
}

class _StatsData {
  const _StatsData({
    required this.days,
    required this.styleShare,
    required this.tagShare,
    required this.popularity,
    required this.timeMinutes,
    required this.sessions,
    required this.activeDays,
    required this.extra,
  });

  factory _StatsData.fromJson(Map<String, dynamic> json) {
    return _StatsData(
      days: (json['range_days'] ?? 30) as int,
      styleShare: ((json['taste_styles'] as List<dynamic>? ?? const [])
          .map((e) => _SliceData.fromJson(e as Map<String, dynamic>))
          .toList()),
      tagShare: ((json['taste_tags'] as List<dynamic>? ?? const [])
          .map((e) => _SliceData.fromJson(e as Map<String, dynamic>))
          .toList()),
      popularity: ((json['popularity'] as List<dynamic>? ?? const [])
          .map((e) => _Point.fromJson(e as Map<String, dynamic>))
          .toList()),
      timeMinutes: (json['time_minutes'] ?? 0) as int,
      sessions: (json['sessions'] ?? 0) as int,
      activeDays: (json['active_days'] ?? 0) as int,
      extra: (json['extra'] as Map<String, dynamic>? ?? const {}).map(
        (k, v) => MapEntry(k, (v as num).toDouble()),
      ),
    );
  }

  final int days;
  final List<_SliceData> styleShare;
  final List<_SliceData> tagShare;
  final List<_Point> popularity;
  final int timeMinutes;
  final int sessions;
  final int activeDays;
  final Map<String, double> extra;
}

class _SliceData {
  const _SliceData({
    required this.label,
    required this.count,
    required this.sharePercent,
  });

  factory _SliceData.fromJson(Map<String, dynamic> json) {
    return _SliceData(
      label: (json['label'] ?? '').toString(),
      count: (json['count'] ?? 0) as int,
      sharePercent: (json['share_percent'] as num?)?.toDouble() ?? 0,
    );
  }

  final String label;
  final int count;
  final double sharePercent;
}

class _Point {
  const _Point({
    required this.date,
    required this.likes,
    required this.views,
    required this.comments,
  });

  factory _Point.fromJson(Map<String, dynamic> json) {
    return _Point(
      date: (json['date'] ?? '').toString(),
      likes: (json['likes'] ?? 0) as int,
      views: (json['views'] ?? 0) as int,
      comments: (json['comments'] ?? 0) as int,
    );
  }

  final String date;
  final int likes;
  final int views;
  final int comments;
}


Widget _legendDot(Color color, String label) {
  return Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
      const SizedBox(width: 6),
      Text(label),
    ],
  );
}

class _DonutPainter extends CustomPainter {
  _DonutPainter(this.values);

  final List<_SliceData> values;

  static const _palette = [
    Color(0xFFFF1B43),
    Color(0xFF1F1F1F),
    Color(0xFF5A5A5A),
    Color(0xFFAFAFAF),
    Color(0xFF777777),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final total = values.fold<double>(0, (sum, v) => sum + v.sharePercent);
    if (total <= 0) {
      return;
    }

    final rect = Offset.zero & size;
    final stroke = math.max(8.0, size.shortestSide * 0.18);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.butt;

    double start = -math.pi / 2;
    for (var i = 0; i < values.length; i++) {
      final sweep = (values[i].sharePercent / total) * math.pi * 2;
      paint.color = _palette[i % _palette.length];
      canvas.drawArc(rect, start, sweep, false, paint);
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) =>
      oldDelegate.values != values;
}

class _LineChartPainter extends CustomPainter {
  _LineChartPainter(this.data);

  final List<_Point> data;

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) {
      return;
    }

    const leftPad = 28.0;
    const bottomPad = 22.0;
    final chartW = size.width - leftPad - 6;
    final chartH = size.height - bottomPad - 6;

    final maxY =
        data
            .map(
              (e) => math.max(
                e.likes.toDouble(),
                math.max(e.views.toDouble(), e.comments.toDouble()),
              ),
            )
            .reduce(math.max) +
        10;

    final axis = Paint()
      ..color = AppColors.ink.withValues(alpha: 0.4)
      ..strokeWidth = 1;

    canvas.drawLine(
      Offset(leftPad, chartH),
      Offset(leftPad + chartW, chartH),
      axis,
    );
    canvas.drawLine(Offset(leftPad, 0), Offset(leftPad, chartH), axis);

    void drawSeries(Color color, double Function(_Point) pick) {
      final p = Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke;
      final path = Path();
      for (var i = 0; i < data.length; i++) {
        final x =
            leftPad +
            (i / (data.length - 1 == 0 ? 1 : data.length - 1)) * chartW;
        final y = chartH - (pick(data[i]) / maxY) * chartH;
        if (i == 0) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
      }
      canvas.drawPath(path, p);
    }

    drawSeries(const Color(0xFFFF1B43), (p) => p.likes.toDouble());
    drawSeries(const Color(0xFF1F1F1F), (p) => p.views.toDouble());
    drawSeries(const Color(0xFF7A7A7A), (p) => p.comments.toDouble());
  }

  @override
  bool shouldRepaint(covariant _LineChartPainter oldDelegate) =>
      oldDelegate.data != data;
}
