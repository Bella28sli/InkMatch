import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:yandex_mapkit/yandex_mapkit.dart';

import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/verify_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/settings_demo_screen.dart';
import 'screens/feed_demo_screen.dart';
import 'screens/post_demo_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/collection_screen.dart';
import 'screens/chat_list_screen.dart';
import 'screens/chat_room_screen.dart';
import 'screens/inkmatch_defaults_screen.dart';
import 'screens/inkmatch_create_screen.dart';
import 'screens/inkmatch_requests_history_screen.dart';
import 'screens/activity_center_screen.dart';
import 'screens/notifications_screen.dart';
import 'screens/complaint_form_screen.dart';
import 'screens/artists_feed_screen.dart';
import 'screens/feed_settings_screen.dart';
import 'screens/create_post_screen.dart';
import 'screens/moderation_queue_screen.dart';
import 'screens/moderation_user_screen.dart';
import 'screens/moderation_stats_screen.dart';
import 'screens/moderation_users_search_screen.dart';
import 'screens/restriction_history_screen.dart';
import 'screens/forgot_password_screen.dart';
import 'screens/master_verification_screen.dart';
import 'screens/master_workplaces_screen.dart';
import 'theme/app_theme.dart';
import 'l10n/app_locale_scope.dart';
import 'services/app_config.dart';
import 'services/push_service.dart';
import 'services/app_session.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  AndroidYandexMap.useAndroidViewSurface = false;
  await AppConfig.init();
  await Firebase.initializeApp();
  await AppSession.instance.restoreAuth();
  runApp(const InkMatchApp());
}

class InkMatchApp extends StatefulWidget {
  const InkMatchApp({super.key});

  @override
  State<InkMatchApp> createState() => _InkMatchAppState();
}

class _InkMatchAppState extends State<InkMatchApp> {
  final _navigatorKey = GlobalKey<NavigatorState>();
  Locale _locale = const Locale('ru');
  bool _isDarkTheme = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      PushService.instance.initialize(_navigatorKey);
    });
  }

  void _toggleLocale() {
    setState(() {
      _locale = _locale.languageCode == 'ru'
          ? const Locale('en')
          : const Locale('ru');
    });
  }

  void _toggleTheme() {
    setState(() {
      _isDarkTheme = !_isDarkTheme;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AppLocaleScope(
      locale: _locale,
      toggle: _toggleLocale,
      isDarkTheme: _isDarkTheme,
      toggleTheme: _toggleTheme,
      child: MaterialApp(
        navigatorKey: _navigatorKey,
        title: 'InkMatch',
        theme: buildTheme(darkMode: _isDarkTheme),
        locale: _locale,
        supportedLocales: const [Locale('ru'), Locale('en')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        initialRoute: SplashScreen.route,
        builder: (context, child) {
          if (child == null) return const SizedBox.shrink();
          return SafeArea(
            top: false,
            left: false,
            right: false,
            minimum: EdgeInsets.only(
              bottom: MediaQuery.of(context).padding.bottom + 8,
            ),
            child: child,
          );
        },
        routes: {
          SplashScreen.route: (_) => const SplashScreen(),
          LoginScreen.route: (_) => const LoginScreen(),
          RegisterScreen.route: (_) => const RegisterScreen(),
          VerifyScreen.route: (_) => const VerifyScreen(),
          SettingsDemoScreen.route: (_) => const SettingsDemoScreen(),
          FeedDemoScreen.route: (_) => const FeedDemoScreen(),
          PostDemoScreen.route: (_) => const PostDemoScreen(),
          ProfileScreen.route: (_) => const ProfileScreen(),
          CollectionScreen.route: (_) => const CollectionScreen(),
          ChatListScreen.route: (_) => const ChatListScreen(),
          ChatRoomScreen.route: (_) => const ChatRoomScreen(),
          InkmatchCreateScreen.route: (_) => const InkmatchCreateScreen(),
          InkmatchRequestsHistoryScreen.route: (_) =>
              const InkmatchRequestsHistoryScreen(),
          InkmatchDefaultsScreen.route: (_) => const InkmatchDefaultsScreen(),
          ActivityCenterScreen.route: (_) => const ActivityCenterScreen(),
          NotificationsScreen.route: (_) => const NotificationsScreen(),
          ComplaintFormScreen.route: (_) => const ComplaintFormScreen(),
          MastersFeedScreen.route: (_) => const MastersFeedScreen(),
          FeedPreferencesScreen.route: (_) => const FeedPreferencesScreen(),
          CreatePostScreen.route: (_) => const CreatePostScreen(),
          ModerationQueueScreen.route: (_) => const ModerationQueueScreen(),
          ModerationUserScreen.route: (_) => const ModerationUserScreen(),
          ModerationStatsScreen.route: (_) => const ModerationStatsScreen(),
          ModerationUsersSearchScreen.route: (_) =>
              const ModerationUsersSearchScreen(),
          RestrictionHistoryScreen.route: (_) =>
              const RestrictionHistoryScreen(),
          ForgotPasswordScreen.route: (_) => const ForgotPasswordScreen(),
          MasterVerificationScreen.route: (_) =>
              const MasterVerificationScreen(),
          MasterWorkplacesScreen.route: (_) => const MasterWorkplacesScreen(),
        },
      ),
    );
  }
}
