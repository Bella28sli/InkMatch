import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'post_demo_screen.dart';

class InkmatchRequestsHistoryScreen extends StatefulWidget {
  const InkmatchRequestsHistoryScreen({super.key});

  static const route = '/inkmatch-requests-history';

  @override
  State<InkmatchRequestsHistoryScreen> createState() =>
      _InkmatchRequestsHistoryScreenState();
}

class _InkmatchRequestsHistoryScreenState
    extends State<InkmatchRequestsHistoryScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _rows = const [];

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
      final res = await _api.getJson(
        '/inkmatch/requests/me',
        accessToken: AppSession.instance.accessToken,
        query: const {'limit': '100', 'offset': '0'},
      );
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }

      final list = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();

      final rows = <Map<String, dynamic>>[];
      for (final item in list) {
        final sketchId = item['sketch_id']?.toString();
        if (sketchId == null || sketchId.isEmpty) {
          rows.add(item);
          continue;
        }
        String? imageUrl;
        String? title;
        final postRes = await _api.getJson(
          '/posts/$sketchId',
          accessToken: AppSession.instance.accessToken,
        );
        if (postRes.statusCode == 200) {
          final post = jsonDecode(postRes.body) as Map<String, dynamic>;
          title = post['title']?.toString();
          final media = post['media_urls'] as List<dynamic>?;
          if (media != null && media.isNotEmpty) {
            imageUrl = media.first.toString();
          }
        }
        rows.add({...item, 'post_title': title, 'post_image_url': imageUrl});
      }

      if (!mounted) return;
      setState(() {
        _rows = rows;
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

  String _statusLabel(String value, bool isRu) {
    return switch (value) {
      'active' => isRu ? 'Активна' : 'Active',
      'matched' => isRu ? 'Есть совпадение' : 'Matched',
      'cancelled' => isRu ? 'Отменена' : 'Cancelled',
      'closed' => isRu ? 'Закрыта' : 'Closed',
      'draft' => isRu ? 'Черновик' : 'Draft',
      _ => value,
    };
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          isRu
              ? 'История заявок InkMatch'
              : 'InkMatch requests history',
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : _rows.isEmpty
          ? Center(
              child: Text(
                isRu
                    ? 'Здесь пока ничего нет'
                    : 'Nothing here yet',
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              ),
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: _rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final row = _rows[index];
                  final sketchId = row['sketch_id']?.toString() ?? '';
                  final imageUrl = row['post_image_url']?.toString();
                  final title = row['post_title']?.toString();
                  final status = row['status']?.toString() ?? '-';
                  final createdAt = row['created_at']?.toString() ?? '';

                  return InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: sketchId.isEmpty
                        ? null
                        : () => Navigator.pushNamed(
                            context,
                            PostDemoScreen.route,
                            arguments: sketchId,
                          ),
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.85),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: AppColors.ink.withValues(alpha: 0.12),
                        ),
                      ),
                      child: Row(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: imageUrl == null || imageUrl.isEmpty
                                ? Container(
                                    width: 76,
                                    height: 76,
                                    color: AppColors.ink,
                                    child: const Icon(
                                      Icons.image_not_supported_outlined,
                                      color: Colors.white,
                                    ),
                                  )
                                : Image.network(
                                    imageUrl,
                                    width: 76,
                                    height: 76,
                                    fit: BoxFit.cover,
                                    errorBuilder: (_, __, ___) => Container(
                                      width: 76,
                                      height: 76,
                                      color: AppColors.ink,
                                      child: const Icon(
                                        Icons.image_not_supported_outlined,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  title == null || title.trim().isEmpty
                                      ? (isRu
                                            ? 'Пост без названия'
                                            : 'Untitled post')
                                      : title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontFamily: AppTypography.headerFont(
                                      locale,
                                    ),
                                    fontSize: 18,
                                    color: AppColors.ink,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  '${isRu ? 'Статус' : 'Status'}: ${_statusLabel(status, isRu)}',
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                  ),
                                ),
                                Text(
                                  createdAt,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    color: AppColors.ink.withValues(alpha: 0.7),
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.chevron_right),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
