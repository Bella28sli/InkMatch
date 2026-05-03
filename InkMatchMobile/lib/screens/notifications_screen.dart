import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'chat_room_screen.dart';
import 'collection_screen.dart';
import 'master_verification_screen.dart';
import 'post_demo_screen.dart';
import 'profile_screen.dart';
import 'restriction_history_screen.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  static const route = '/notifications';

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  String? get _token => AppSession.instance.accessToken;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await _api.getJson(
        '/notifications',
        accessToken: _token,
        query: const {'limit': '100', 'offset': '0'},
      );
      if (!mounted) return;

      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Не удалось загрузить уведомления'
                : 'Failed to load notifications',
          );
        });
        return;
      }

      final data = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();

      setState(() {
        _items = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _markRead(String id) async {
    await _api.postJson(
      '/notifications/$id/read',
      const {},
      accessToken: _token,
    );
  }

  Future<void> _openNotification(Map<String, dynamic> item) async {
    final id = item['id']?.toString() ?? '';
    if (id.isNotEmpty && item['is_read'] != true) {
      await _markRead(id);
      if (mounted) {
        setState(() => item['is_read'] = true);
      }
    }
    if (!mounted) return;

    final deepLink = item['deep_link']?.toString();
    if (deepLink != null &&
        deepLink.isNotEmpty &&
        deepLink.trim() != '/notifications') {
      _navigateByDeepLink(deepLink);
      return;
    }

    if (id.isEmpty) return;
    final linksRes = await _api.getJson(
      '/notifications/$id/links',
      accessToken: _token,
    );
    if (linksRes.statusCode != 200) return;

    final links = (jsonDecode(linksRes.body) as List<dynamic>)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    if (links.isEmpty) return;
    if (!mounted) return;

    String? idOf(String type) {
      for (final link in links) {
        if (link['entity_type']?.toString() == type) {
          final id = link['entity_id']?.toString();
          if (id != null && id.isNotEmpty) return id;
        }
      }
      return null;
    }

    final sketchId = idOf('sketch');
    final chatId = idOf('chat');
    final messageId = idOf('message');
    final commentId = idOf('comment');
    final restrictionId = idOf('user_restriction');
    final appealId = idOf('appeal');
    final userId = idOf('user');
    final collectionId = idOf('collection');

    if (commentId != null && sketchId != null) {
      Navigator.pushNamed(context, PostDemoScreen.route, arguments: sketchId);
      return;
    }
    if (messageId != null && chatId != null) {
      Navigator.pushNamed(
        context,
        ChatRoomScreen.route,
        arguments: ChatRoomScreenArgs(chatId: chatId),
      );
      return;
    }
    if (restrictionId != null || appealId != null || idOf('warning') != null) {
      Navigator.pushNamed(context, RestrictionHistoryScreen.route);
      return;
    }

    final first = links.first;
    final entityType = first['entity_type']?.toString() ?? '';
    final entityId = first['entity_id']?.toString() ?? '';
    if (entityType == 'sketch' && entityId.isNotEmpty) {
      Navigator.pushNamed(context, PostDemoScreen.route, arguments: entityId);
    } else if ((entityType == 'chat' || entityType == 'message') && (chatId ?? entityId).isNotEmpty) {
      Navigator.pushNamed(
        context,
        ChatRoomScreen.route,
        arguments: ChatRoomScreenArgs(chatId: chatId ?? entityId),
      );
    } else if (userId != null || (entityType == 'user' && entityId.isNotEmpty)) {
      Navigator.pushNamed(
        context,
        ProfileScreen.route,
        arguments: ProfileScreenArgs(userId: userId ?? entityId),
      );
    } else if (collectionId != null || (entityType == 'collection' && entityId.isNotEmpty)) {
      Navigator.pushNamed(
        context,
        CollectionScreen.route,
        arguments: CollectionScreenArgs(collectionId: collectionId ?? entityId, isOwner: false),
      );
    } else if ((entityType == 'user_restriction' || entityType == 'appeal') && entityId.isNotEmpty) {
      Navigator.pushNamed(context, RestrictionHistoryScreen.route);
    }
  }

  void _navigateByDeepLink(String deepLink) {
    final normalized = deepLink.trim();
    final parts = normalized.split('/').where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return;

    final head = parts.first;
    if (head == 'post' && parts.length > 1) {
      Navigator.pushNamed(context, PostDemoScreen.route, arguments: parts[1]);
      return;
    }
    if (head == 'profile' && parts.length > 1) {
      Navigator.pushNamed(
        context,
        ProfileScreen.route,
        arguments: ProfileScreenArgs(userId: parts[1]),
      );
      return;
    }
    if (head == 'chat' && parts.length > 1) {
      Navigator.pushNamed(
        context,
        ChatRoomScreen.route,
        arguments: ChatRoomScreenArgs(chatId: parts[1]),
      );
      return;
    }
    if (head == 'collection' && parts.length > 1) {
      Navigator.pushNamed(
        context,
        CollectionScreen.route,
        arguments: CollectionScreenArgs(collectionId: parts[1], isOwner: false),
      );
      return;
    }
    if (head == 'master-verification') {
      Navigator.pushNamed(context, MasterVerificationScreen.route);
      return;
    }
    if (head == 'account' && parts.length > 1 && parts[1] == 'restrictions') {
      Navigator.pushNamed(context, RestrictionHistoryScreen.route);
      return;
    }
  }

  bool _hasNavigationTarget(Map<String, dynamic> item) {
    final deepLink = item['deep_link']?.toString();
    if (deepLink != null && deepLink.trim().isNotEmpty) return true;
    final count = item['links_count'];
    if (count is num && count > 0) return true;
    return false;
  }

  Future<void> _markAllRead() async {
    await _api.postJson(
      '/notifications/read-all',
      const {},
      accessToken: _token,
    );
    if (!mounted) return;
    setState(() {
      _items = _items.map((e) => {...e, 'is_read': true}).toList();
    });
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
          isRu ? 'Уведомления' : 'Notifications',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
        actions: [
          TextButton(
            onPressed: _items.isEmpty ? null : _markAllRead,
            child: Text(
              isRu ? 'Прочитать все' : 'Read all',
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : _items.isEmpty
          ? Center(
              child: Text(
                isRu ? 'Пока нет уведомлений' : 'No notifications yet',
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              ),
            )
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                itemCount: _items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final item = _items[index];
                  final isRead = item['is_read'] == true;
                  return InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: () => _openNotification(item),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isRead
                            ? Colors.white.withValues(alpha: 0.8)
                            : Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isRead
                              ? AppColors.ink.withValues(alpha: 0.14)
                              : AppColors.accent.withValues(alpha: 0.5),
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: isRead
                                  ? Colors.transparent
                                  : AppColors.accent,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item['title']?.toString() ?? '',
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.ink,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  item['body']?.toString() ?? '',
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  item['created_at']?.toString() ?? '',
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    fontSize: 11,
                                    color: AppColors.ink.withValues(
                                      alpha: 0.65,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (_hasNavigationTarget(item))
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
