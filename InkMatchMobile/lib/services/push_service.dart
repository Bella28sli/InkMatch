import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';

import '../screens/chat_room_screen.dart';
import '../screens/collection_screen.dart';
import '../screens/feed_demo_screen.dart';
import '../screens/login_screen.dart';
import '../screens/notifications_screen.dart';
import '../screens/post_demo_screen.dart';
import '../screens/profile_screen.dart';
import 'api_client.dart';
import 'app_session.dart';

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}

class PushService {
  PushService._();

  static final PushService instance = PushService._();

  final _api = ApiClient.defaultClient();
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  GlobalKey<NavigatorState>? _navigatorKey;
  StreamSubscription<String>? _tokenSubscription;

  Future<void> initialize(GlobalKey<NavigatorState> navigatorKey) async {
    _navigatorKey = navigatorKey;

    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    await _messaging.setAutoInitEnabled(true);

    FirebaseMessaging.onMessageOpenedApp.listen(_handleMessageOpen);

    final initialMessage = await _messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleMessageOpen(initialMessage);
    }

    _tokenSubscription?.cancel();
    _tokenSubscription = _messaging.onTokenRefresh.listen((token) {
      unawaited(_registerToken(token));
    });
  }

  Future<void> requestPermissions() async {
    await _messaging.requestPermission(alert: true, badge: true, sound: true);
  }

  Future<void> registerCurrentDeviceToken() async {
    await requestPermissions();
    final token = await _messaging.getToken();
    if (token == null || token.isEmpty) return;
    await _registerToken(token);
  }

  Future<void> _registerToken(String token) async {
    final accessToken = AppSession.instance.accessToken;
    if (accessToken == null || accessToken.isEmpty) return;

    try {
      await _api.postJson('/notifications/push-token', {
        'platform': 'android',
        'token': token,
      }, accessToken: accessToken);
    } catch (_) {
      // Do not fail user flow on push registration errors.
    }
  }

  Future<void> unregisterCurrentDeviceToken() async {
    final accessToken = AppSession.instance.accessToken;
    if (accessToken == null || accessToken.isEmpty) return;

    try {
      final token = await _messaging.getToken();
      if (token == null || token.isEmpty) return;
      await _api.deleteJson(
        '/notifications/push-token?token=$token',
        accessToken: accessToken,
      );
    } catch (_) {
      // Ignore token removal errors on logout path.
    }
  }

  void _handleMessageOpen(RemoteMessage message) {
    final deepLink = message.data['deep_link']?.toString();
    if (deepLink == null || deepLink.isEmpty) {
      _navigatorKey?.currentState?.pushNamed(NotificationsScreen.route);
      return;
    }
    _navigateByDeepLink(deepLink);
  }

  void _navigateByDeepLink(String deepLink) {
    final nav = _navigatorKey?.currentState;
    if (nav == null) return;

    final parts = deepLink.split('/').where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) {
      nav.pushNamed(FeedDemoScreen.route);
      return;
    }

    if (parts.first == 'post' && parts.length > 1) {
      nav.pushNamed(PostDemoScreen.route, arguments: parts[1]);
      return;
    }
    if (parts.first == 'chat' && parts.length > 1) {
      nav.pushNamed(
        ChatRoomScreen.route,
        arguments: ChatRoomScreenArgs(chatId: parts[1]),
      );
      return;
    }
    if (parts.first == 'profile' && parts.length > 1) {
      nav.pushNamed(
        ProfileScreen.route,
        arguments: ProfileScreenArgs(userId: parts[1]),
      );
      return;
    }
    if (parts.first == 'collection' && parts.length > 1) {
      nav.pushNamed(
        CollectionScreen.route,
        arguments: CollectionScreenArgs(collectionId: parts[1], isOwner: false),
      );
      return;
    }

    if (parts.first == 'login') {
      nav.pushNamed(LoginScreen.route);
      return;
    }

    nav.pushNamed(NotificationsScreen.route);
  }
}
