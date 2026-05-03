import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'chat_room_screen.dart';

class ChatListScreenArgs {
  const ChatListScreenArgs({this.startWithUserId, this.startWithNickname});

  final String? startWithUserId;
  final String? startWithNickname;
}

class ChatListScreen extends StatefulWidget {
  const ChatListScreen({super.key});

  static const route = '/chats';

  @override
  State<ChatListScreen> createState() => _ChatListScreenState();
}

class _ChatListScreenState extends State<ChatListScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  bool _openingInitialChat = false;
  String? _error;
  List<Map<String, dynamic>> _chats = const [];
  bool _initialHandled = false;

  String? get _token => AppSession.instance.accessToken;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loading) {
      _loadChats();
    }
  }

  Future<void> _loadChats() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _loading = false;
        _error = AppLocaleScope.of(context).locale.languageCode == 'ru'
            ? 'Нужна авторизация'
            : 'Not authenticated';
      });
      return;
    }

    try {
      final res = await _api.getJson('/chats', accessToken: _token);
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
                ? 'Не удалось загрузить чаты'
                : 'Failed to load chats',
          );
        });
        return;
      }

      final data = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList();

      setState(() {
        _chats = data;
        _loading = false;
      });

      await _openInitialDirectIfNeeded();
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

  Future<void> _openInitialDirectIfNeeded() async {
    if (_initialHandled || !mounted) {
      return;
    }
    _initialHandled = true;

    final args = ModalRoute.of(context)?.settings.arguments;
    final screenArgs = args is ChatListScreenArgs ? args : null;
    final userId = screenArgs?.startWithUserId;

    if (userId == null || userId.isEmpty || _token == null || _token!.isEmpty) {
      return;
    }

    setState(() {
      _openingInitialChat = true;
    });

    try {
      final res = await _api.postJson('/chats/direct', {
        'user_id': userId,
      }, accessToken: _token);

      if (!mounted) {
        return;
      }

      if (res.statusCode != 201) {
        setState(() {
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Не удалось открыть чат'
                : 'Failed to open chat',
          );
          _openingInitialChat = false;
        });
        return;
      }

      final chat = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _openingInitialChat = false;
      });

      await Navigator.pushNamed(
        context,
        ChatRoomScreen.route,
        arguments: ChatRoomScreenArgs(
          chatId: chat['id']?.toString() ?? '',
          peerUserId: chat['other_user_id']?.toString(),
          peerNickname:
              chat['other_nickname']?.toString() ??
              screenArgs?.startWithNickname,
        ),
      );

      if (mounted) {
        await _loadChats();
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _openingInitialChat = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _openChat(Map<String, dynamic> chat) async {
    final chatId = chat['id']?.toString();
    if (chatId == null || chatId.isEmpty) {
      return;
    }

    await Navigator.pushNamed(
      context,
      ChatRoomScreen.route,
      arguments: ChatRoomScreenArgs(
        chatId: chatId,
        peerUserId: chat['other_user_id']?.toString(),
        peerNickname: chat['other_nickname']?.toString(),
      ),
    );

    if (mounted) {
      await _loadChats();
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          isRu ? 'Чаты' : 'Chats',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.ink,
      ),
      body: Column(
        children: [
          if (_openingInitialChat)
            const LinearProgressIndicator(color: AppColors.accent),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        _error!,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                        ),
                      ),
                    ),
                  )
                : _chats.isEmpty
                ? Center(
                    child: Text(
                      isRu ? 'Пока нет чатов' : 'No chats yet',
                      style: TextStyle(
                        fontFamily: AppTypography.bodyFont(locale),
                      ),
                    ),
                  )
                : RefreshIndicator(
                    onRefresh: _loadChats,
                    child: ListView.separated(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      itemCount: _chats.length,
                      separatorBuilder: (context, index) =>
                          const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final chat = _chats[index];
                        final name = chat['other_nickname']?.toString();
                        final subtitle = chat['last_message_text']?.toString();
                        return ListTile(
                          onTap: () => _openChat(chat),
                          leading: const CircleAvatar(
                            backgroundColor: AppColors.ink,
                            child: Icon(Icons.person, color: Colors.white),
                          ),
                          title: Text(
                            (name == null || name.isEmpty)
                                ? (isRu ? 'Пользователь' : 'User')
                                : name,
                            style: TextStyle(
                              fontFamily: AppTypography.bodyFont(locale),
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          subtitle: Text(
                            (subtitle == null || subtitle.isEmpty)
                                ? (isRu ? 'Нет сообщений' : 'No messages')
                                : subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontFamily: AppTypography.bodyFont(locale),
                              color: AppColors.ink.withValues(alpha: 0.75),
                            ),
                          ),
                          trailing: _UnreadBadge(
                            unreadCount: (chat['unread_count'] as num?)?.toInt() ?? 0,
                          ),
                        );
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}


class _UnreadBadge extends StatelessWidget {
  const _UnreadBadge({required this.unreadCount});

  final int unreadCount;

  @override
  Widget build(BuildContext context) {
    if (unreadCount <= 0) {
      return const Icon(Icons.chevron_right);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.accent,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        unreadCount > 99 ? '99+' : '$unreadCount',
        style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
