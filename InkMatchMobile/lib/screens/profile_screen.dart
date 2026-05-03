import 'dart:io';
import 'dart:convert';

import 'package:http_parser/http_parser.dart';

import 'package:flutter/material.dart';
import '../l10n/app_locale_scope.dart';
import '../services/avatar_picker.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'collection_screen.dart';
import 'settings_demo_screen.dart';
import 'chat_list_screen.dart';
import 'complaint_form_screen.dart';
import 'inkmatch_requests_history_screen.dart';
import 'master_verification_screen.dart';
import 'master_workplaces_screen.dart';

enum ProfileRole { client, master }

class ProfileScreenArgs {
  const ProfileScreenArgs({this.userId});

  final String? userId;
}

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  static const route = '/profile';

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  bool _isSubscribed = false;
  bool _subBusy = false;

  Map<String, dynamic>? _profile;
  List<Map<String, dynamic>> _collections = const [];
  List<Map<String, dynamic>> _masterReviews = const [];

  String? get _token => AppSession.instance.accessToken;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_profile != null || _error != null) return;
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    final args = ModalRoute.of(context)?.settings.arguments;
    final screenArgs = args is ProfileScreenArgs
        ? args
        : const ProfileScreenArgs();

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _loading = false;
        _error =
            'Требуется авторизация';
      });
      return;
    }

    try {
      final profilePath = screenArgs.userId == null
          ? '/profiles/me/full'
          : '/profiles/${screenArgs.userId}/full';

      final profileRes = await _api.getJson(profilePath, accessToken: _token);
      if (profileRes.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${profileRes.statusCode}: ${profileRes.body}';
        });
        return;
      }

      final profile = jsonDecode(profileRes.body) as Map<String, dynamic>;
      final ownerId = profile['user_id'].toString();
      final section = profile['role'] == 'master' ? 'master' : null;

      final collectionsRes = await _api.getJson(
        '/collections',
        accessToken: _token,
        query: {'owner_id': ownerId, if (section != null) 'section': section},
      );
      if (collectionsRes.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${collectionsRes.statusCode}: ${collectionsRes.body}';
        });
        return;
      }

      final collectionsData = (jsonDecode(collectionsRes.body) as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList();

      var masterReviews = const <Map<String, dynamic>>[];
      if (profile['role'] == 'master') {
        final reviewsRes = await _api.getJson(
          '/profiles/$ownerId/reviews',
          accessToken: _token,
          query: const {'limit': '50', 'offset': '0'},
        );
        if (reviewsRes.statusCode == 200) {
          masterReviews = (jsonDecode(reviewsRes.body) as List<dynamic>)
              .map((e) => e as Map<String, dynamic>)
              .toList();
        }
      }

      var subscribed = false;
      final isOwner = (profile['is_owner'] ?? false) == true;
      if (!isOwner) {
        final statusRes = await _api.getJson(
          '/subscriptions/status',
          accessToken: _token,
          query: {'target_user_id': ownerId},
        );
        if (statusRes.statusCode == 200) {
          final payload = jsonDecode(statusRes.body) as Map<String, dynamic>;
          subscribed = (payload['is_subscribed'] ?? false) == true;
        }
      }

      setState(() {
        _profile = profile;
        _collections = collectionsData;
        _masterReviews = masterReviews;
        _isSubscribed = subscribed;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _toggleSubscribe() async {
    if (_subBusy || _profile == null) return;
    final targetId = _profile!['user_id'].toString();

    setState(() => _subBusy = true);
    try {
      final res = _isSubscribed
          ? await _api.deleteJson(
              '/subscriptions/$targetId',
              accessToken: _token,
            )
          : await _api.postJson(
              '/subscriptions/$targetId',
              {},
              accessToken: _token,
            );

      if (res.statusCode == 204) {
        setState(() {
          _isSubscribed = !_isSubscribed;
          final followers = (_profile!['followers_count'] ?? 0) as int;
          _profile!['followers_count'] = _isSubscribed
              ? followers + 1
              : followers - 1;
        });
      } else {
        _showMessage('${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      _showMessage('$e');
    } finally {
      if (mounted) {
        setState(() => _subBusy = false);
      }
    }
  }

  Future<void> _openEditProfile() async {
    if (_profile == null) return;
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final nicknameCtrl = TextEditingController(
      text: _profile!['nickname']?.toString() ?? '',
    );
    final bioCtrl = TextEditingController(
      text: _profile!['bio']?.toString() ?? '',
    );

    String? pickedAvatarPath = AppSession.instance.localAvatarPath;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Container(
              decoration: const BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.vertical(top: Radius.circular(22)),
              ),
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(context).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isRu
                        ? 'Редактировать профиль'
                        : 'Edit profile',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 24,
                    ),
                  ),
                  const SizedBox(height: 10),
                  GestureDetector(
                    onTap: () async {
                      final source = await AvatarPicker.chooseSource(context);
                      if (source == null) return;
                      final file = await AvatarPicker.pickAndCrop(
                        context,
                        source: source,
                      );
                      if (file == null) return;
                      setSheetState(() => pickedAvatarPath = file.path);
                    },
                    child: CircleAvatar(
                      radius: 36,
                      backgroundColor: AppColors.ink,
                      backgroundImage:
                          (pickedAvatarPath != null &&
                              pickedAvatarPath!.isNotEmpty)
                          ? FileImage(File(pickedAvatarPath!))
                          : null,
                      child: pickedAvatarPath == null
                          ? const Icon(Icons.add_a_photo, color: Colors.white)
                          : null,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    isRu
                        ? 'Аватар можно выбрать из галереи или сделать фото'
                        : 'Choose an avatar from gallery or take a photo',
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: AppColors.ink.withValues(alpha: 0.8),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: nicknameCtrl,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Никнейм'
                          : 'Nickname',
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: bioCtrl,
                    maxLines: 3,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Обо мне'
                          : 'About me',
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () async {
                        final res = await _api.patchJson('/profiles/me', {
                          'nickname': nicknameCtrl.text.trim(),
                          'bio': bioCtrl.text.trim().isEmpty
                              ? null
                              : bioCtrl.text.trim(),
                        }, accessToken: _token);
                        if (!mounted) return;
                        if (res.statusCode == 200) {
                          if (pickedAvatarPath != null &&
                              pickedAvatarPath!.isNotEmpty) {
                            final file = File(pickedAvatarPath!);
                            if (file.existsSync()) {
                              final avatarRes = await _api.postMultipart(
                                '/profiles/me/avatar',
                                file: file,
                                fieldName: 'file',
                                contentType: file.path.toLowerCase().endsWith('.png')
                                    ? MediaType('image', 'png')
                                    : file.path.toLowerCase().endsWith('.webp')
                                        ? MediaType('image', 'webp')
                                        : MediaType('image', 'jpeg'),
                                accessToken: _token,
                              );
                              if (avatarRes.statusCode == 200) {
                                final avatarPayload =
                                    jsonDecode(avatarRes.body)
                                        as Map<String, dynamic>;
                                _profile!['avatar_url'] =
                                    avatarPayload['avatar_url'];
                                AppSession.instance.setLocalAvatarPath(null);
                                AppSession.instance.clearPendingAvatarUpload();
                              }
                            }
                          }
                          if (AppSession.instance.localAvatarPath == null) {
                            AppSession.instance.setLocalAvatarPath(null);
                          }
                          Navigator.pop(context);
                          setState(() {
                            _profile!['nickname'] = nicknameCtrl.text.trim();
                            _profile!['bio'] = bioCtrl.text.trim().isEmpty
                                ? null
                                : bioCtrl.text.trim();
                          });
                        } else {
                          _showMessage('${res.statusCode}: ${res.body}');
                        }
                      },
                      child: Text(
                        isRu
                            ? 'Сохранить'
                            : 'Save',
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _createCollection() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final titleCtrl = TextEditingController();
    final descriptionCtrl = TextEditingController();
    var isPrivate = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(context).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isRu
                        ? 'Новая коллекция'
                        : 'New collection',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 24,
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: titleCtrl,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Название'
                          : 'Title',
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: descriptionCtrl,
                    maxLines: 3,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Описание'
                          : 'Description',
                    ),
                  ),
                  SwitchListTile(
                    value: isPrivate,
                    contentPadding: EdgeInsets.zero,
                    onChanged: (v) => setSheetState(() => isPrivate = v),
                    title: Text(
                      isRu
                          ? 'Приватная коллекция'
                          : 'Private collection',
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () async {
                        final title = titleCtrl.text.trim();
                        if (title.isEmpty) {
                          _showMessage(
                            isRu
                                ? 'Введите название'
                                : 'Enter title',
                          );
                          return;
                        }
                        final res = await _api.postJson('/collections', {
                          'title': title,
                          'description': descriptionCtrl.text.trim(),
                          'collection_type': 'custom',
                          'is_private': isPrivate,
                        }, accessToken: _token);
                        if (!mounted) return;
                        if (res.statusCode == 201) {
                          Navigator.pop(context);
                          await _load();
                        } else {
                          _showMessage('${res.statusCode}: ${res.body}');
                        }
                      },
                      child: Text(
                        isRu
                            ? 'Создать'
                            : 'Create',
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _deleteCollection(String collectionId) async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isRu
              ? 'Удалить коллекцию?'
              : 'Delete collection?',
        ),
        content: Text(
          isRu
              ? 'Это действие нельзя отменить.'
              : 'This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(
              isRu ? 'Отмена' : 'Cancel',
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(
              isRu ? 'Удалить' : 'Delete',
            ),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final res = await _api.deleteJson(
      '/collections/$collectionId',
      accessToken: _token,
    );
    if (!mounted) return;
    if (res.statusCode == 204) {
      await _load();
    } else {
      _showMessage('${res.statusCode}: ${res.body}');
    }
  }

  void _showMessage(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_error != null) {
      return Scaffold(body: Center(child: Text(_error!)));
    }

    final profile = _profile!;
    final role = profile['role'] == 'master'
        ? ProfileRole.master
        : ProfileRole.client;
    final isOwner = (profile['is_owner'] ?? false) == true;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
          children: [
            _TopBar(
              isOwner: isOwner,
              onSettings: () =>
                  Navigator.pushNamed(context, SettingsDemoScreen.route),
              onEdit: _openEditProfile,
              isRu: isRu,
            ),
            const SizedBox(height: 8),
            _HeroProfileCard(
              profile: profile,
              role: role,
              isRu: isRu,
              isOwner: isOwner,
              localAvatarPath: AppSession.instance.localAvatarPath,
            ),
            const SizedBox(height: 10),
            if (isOwner &&
                role == ProfileRole.master &&
                (profile['verification_skipped'] ?? false) == true)
              _VerificationWarning(
                isRu: isRu,
                onTap: () => Navigator.pushNamed(
                  context,
                  MasterVerificationScreen.route,
                ).then((_) => _load()),
              ),
            if (isOwner &&
                role == ProfileRole.master &&
                (profile['verification_skipped'] ?? false) == true)
              const SizedBox(height: 10),
            if (isOwner &&
                role == ProfileRole.master &&
                (profile['is_verified'] ?? false) != true &&
                (profile['verification_skipped'] ?? false) != true)
              _VerificationPrompt(
                isRu: isRu,
                onTap: () => Navigator.pushNamed(
                  context,
                  MasterVerificationScreen.route,
                ).then((_) => _load()),
              ),
            if (isOwner &&
                role == ProfileRole.master &&
                (profile['is_verified'] ?? false) != true &&
                (profile['verification_skipped'] ?? false) != true)
              const SizedBox(height: 10),
            if (!isOwner)
              _ActionButtons(
                isRu: isRu,
                isSubscribed: _isSubscribed,
                busy: _subBusy,
                onSubscribe: _toggleSubscribe,
                onMessage: () {
                  final userId = profile['user_id']?.toString();
                  if (userId == null || userId.isEmpty) {
                    return;
                  }
                  Navigator.pushNamed(
                    context,
                    ChatListScreen.route,
                    arguments: ChatListScreenArgs(
                      startWithUserId: userId,
                      startWithNickname: profile['nickname']?.toString(),
                    ),
                  );
                },
                onReport: () => Navigator.pushNamed(
                  context,
                  ComplaintFormScreen.route,
                  arguments: ComplaintFormArgs(
                    targetType: 'user',
                    targetId: profile['user_id'].toString(),
                    targetTitle: profile['nickname']?.toString(),
                  ),
                ),
              ),
            if (isOwner && role == ProfileRole.master)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                child: OutlinedButton.icon(
                  onPressed: () async {
                    await Navigator.pushNamed(
                      context,
                      MasterWorkplacesScreen.route,
                    );
                    _load();
                  },
                  icon: const Icon(Icons.place),
                  label: Text(
                    isRu ? 'Адреса и студии' : 'Addresses and studios',
                  ),
                ),
              ),
            if (!isOwner) const SizedBox(height: 10),
            if (role == ProfileRole.master)
              _MasterInfo(
                isRu: isRu,
                address: _valueOrEmpty(
                  profile['master_address']?.toString(),
                  isRu,
                ),
                about: _valueOrEmpty(profile['bio']?.toString(), isRu),
              ),
            if (role == ProfileRole.master) const SizedBox(height: 10),
            if (role == ProfileRole.master)
              _MasterReviewsBlock(reviews: _masterReviews, isRu: isRu),
            if (role == ProfileRole.master) const SizedBox(height: 10),
            if (isOwner)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => Navigator.pushNamed(
                      context,
                      InkmatchRequestsHistoryScreen.route,
                    ),
                    icon: const Icon(Icons.history),
                    label: Text(
                      isRu
                          ? 'История заявок InkMatch'
                          : 'InkMatch requests history',
                    ),
                  ),
                ),
              ),
            _CollectionsBlock(
              title: role == ProfileRole.master
                  ? (isRu
                        ? 'Коллекции мастера'
                        : 'Master collections')
                  : (isRu
                        ? 'Коллекции'
                        : 'Collections'),
              collections: _collections,
              isRu: isRu,
              isOwner: isOwner,
              onCreateCollection: _createCollection,
              onDeleteCollection: _deleteCollection,
            ),
          ],
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.isOwner,
    required this.onSettings,
    required this.onEdit,
    required this.isRu,
  });

  final bool isOwner;
  final VoidCallback onSettings;
  final VoidCallback onEdit;
  final bool isRu;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back, color: AppColors.ink),
        ),
        const Spacer(),
        if (isOwner)
          IconButton(
            tooltip: isRu
                ? 'Редактировать профиль'
                : 'Edit profile',
            onPressed: onEdit,
            icon: const Icon(Icons.edit, color: AppColors.ink),
          ),
        if (isOwner)
          IconButton(
            tooltip: isRu
                ? 'Настройки'
                : 'Settings',
            onPressed: onSettings,
            icon: const Icon(Icons.settings_outlined, color: AppColors.ink),
          ),
      ],
    );
  }
}

class _HeroProfileCard extends StatelessWidget {
  const _HeroProfileCard({
    required this.profile,
    required this.role,
    required this.isRu,
    required this.isOwner,
    required this.localAvatarPath,
  });

  final Map<String, dynamic> profile;
  final ProfileRole role;
  final bool isRu;
  final bool isOwner;
  final String? localAvatarPath;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final avatarUrl = profile['avatar_url']?.toString();
    final localFile =
        (isOwner && localAvatarPath != null && localAvatarPath!.isNotEmpty)
        ? File(localAvatarPath!)
        : null;
    final hasLocalAvatar = localFile != null && localFile.existsSync();

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          CircleAvatar(
            radius: 52,
            backgroundColor: AppColors.ink,
            backgroundImage: hasLocalAvatar
                ? FileImage(localFile)
                : (avatarUrl != null && avatarUrl.isNotEmpty
                          ? NetworkImage(avatarUrl)
                          : null)
                      as ImageProvider<Object>?,
            child: (!hasLocalAvatar && (avatarUrl == null || avatarUrl.isEmpty))
                ? const Icon(Icons.person, color: Colors.white, size: 40)
                : null,
          ),
          const SizedBox(height: 10),
          Text(
            '${_valueOrEmpty(profile['nickname']?.toString(), isRu)}${(role == ProfileRole.master && (profile['is_favorite'] ?? false) == true) ? ' ★' : ''}',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 30,
              color:
                  (role == ProfileRole.master &&
                      (profile['is_favorite'] ?? false) == true)
                  ? Colors.amber.shade800
                  : AppColors.ink,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: [
              _StatBadge(
                label: isRu
                    ? 'Подписчики'
                    : 'Followers',
                value: (profile['followers_count'] ?? 0).toString(),
              ),
              if (role == ProfileRole.client)
                _StatBadge(
                  label: isRu
                      ? 'Отзывы'
                      : 'Reviews',
                  value: (profile['client_reviews_count'] ?? 0).toString(),
                ),
              if (role == ProfileRole.master)
                _StatBadge(
                  label: isRu
                      ? 'Работы'
                      : 'Works',
                  value: (profile['master_completed_works'] ?? 0).toString(),
                ),
              if (role == ProfileRole.master &&
                  (profile['is_verified'] ?? false) == true)
                _StatBadge(label: isRu ? 'Проверен' : 'Verified', value: '✓'),
              if (role == ProfileRole.master &&
                  (profile['is_favorite'] ?? false) == true)
                _StatBadge(
                  label: isRu ? 'Фаворит InkMatch' : 'InkMatch favorite',
                  value: '★',
                ),
            ],
          ),
          if (role == ProfileRole.master) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(5, (index) {
                final rating =
                    (profile['master_rating'] as num?)?.toDouble() ?? 0;
                final starNumber = index + 1;
                final filled = rating >= starNumber;
                final half = !filled && rating >= starNumber - 0.5;
                return Icon(
                  filled
                      ? Icons.star
                      : (half ? Icons.star_half : Icons.star_border),
                  color: Colors.amber,
                  size: 20,
                );
              }),
            ),
          ],
        ],
      ),
    );
  }
}

class _VerificationPrompt extends StatelessWidget {
  const _VerificationPrompt({required this.isRu, required this.onTap});

  final bool isRu;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.accent.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.accent.withValues(alpha: 0.45)),
      ),
      child: Row(
        children: [
          const Icon(Icons.verified_user_outlined, color: AppColors.accent),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              isRu
                  ? 'Пройдите верификацию, чтобы получить отметку в профиле'
                  : 'Verify your profile to get a public badge',
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
          ),
          TextButton(onPressed: onTap, child: Text(isRu ? 'Начать' : 'Start')),
        ],
      ),
    );
  }
}

class _VerificationWarning extends StatelessWidget {
  const _VerificationWarning({required this.isRu, required this.onTap});

  final bool isRu;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.6), width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  isRu ? 'Пройдите верификацию' : 'Complete verification',
                  style: TextStyle(
                    fontFamily: AppTypography.headerFont(locale),
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.orange,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            isRu
                ? 'Верификация помогает повысить ваш рейтинг и доверие клиентов. Вы сможете пройти её позже.'
                : 'Verification helps increase your rating and client trust. You can complete it later.',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onTap,
              icon: const Icon(Icons.verified_user_outlined),
              label: Text(isRu ? 'Пройти верификацию' : 'Verify now'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionButtons extends StatelessWidget {
  const _ActionButtons({
    required this.isRu,
    required this.isSubscribed,
    required this.busy,
    required this.onSubscribe,
    required this.onMessage,
    required this.onReport,
  });

  final bool isRu;
  final bool isSubscribed;
  final bool busy;
  final VoidCallback onSubscribe;
  final VoidCallback onMessage;
  final VoidCallback onReport;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Row(
      children: [
        Expanded(
          child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: isSubscribed ? AppColors.ink : AppColors.accent,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
            onPressed: busy ? null : onSubscribe,
            child: Text(
              busy
                  ? (isRu ? '...' : '...')
                  : (isSubscribed
                        ? (isRu
                              ? 'Вы подписаны'
                              : 'Following')
                        : (isRu
                              ? 'Подписаться'
                              : 'Follow')),
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.ink,
              side: const BorderSide(color: AppColors.ink),
              padding: const EdgeInsets.symmetric(vertical: 12),
              backgroundColor: AppColors.background,
            ),
            onPressed: onMessage,
            icon: const Icon(Icons.chat_bubble_outline),
            label: Text(
              isRu
                  ? 'Написать'
                  : 'Start chat',
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
          ),
        ),

        const SizedBox(width: 8),
        IconButton.filledTonal(
          onPressed: onReport,
          style: IconButton.styleFrom(
            backgroundColor: AppColors.ink.withValues(alpha: 0.1),
            foregroundColor: AppColors.ink,
          ),
          icon: const Icon(Icons.flag_outlined),
        ),
      ],
    );
  }
}

class _MasterInfo extends StatelessWidget {
  const _MasterInfo({
    required this.isRu,
    required this.address,
    required this.about,
  });

  final bool isRu;
  final String address;
  final String about;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isRu ? 'Адрес' : 'Address',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 20,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            address,
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          const SizedBox(height: 10),
          Text(
            isRu ? 'Обо мне' : 'About me',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 20,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            about,
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
        ],
      ),
    );
  }
}

class _MasterReviewsBlock extends StatelessWidget {
  const _MasterReviewsBlock({required this.reviews, required this.isRu});

  final List<Map<String, dynamic>> reviews;
  final bool isRu;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isRu
                ? 'Отзывы клиентов'
                : 'Client reviews',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 22,
            ),
          ),
          const SizedBox(height: 8),
          if (reviews.isEmpty)
            Text(
              isRu
                  ? 'Здесь пока ничего нет'
                  : 'Nothing here yet',
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                color: AppColors.ink.withValues(alpha: 0.75),
              ),
            )
          else
            ...reviews.map((item) {
              final reviewerNickname =
                  item['reviewer_nickname']?.toString() ??
                  (isRu ? 'Клиент' : 'Client');
              final reviewerAvatar = item['reviewer_avatar_url']?.toString();
              final rating = (item['rating_overall'] as num?)?.toInt() ?? 0;
              final body = item['body']?.toString();
              final createdRaw = item['created_at']?.toString();
              final createdAt = createdRaw == null
                  ? ''
                  : _formatDate(createdRaw);
              final attachments =
                  (item['attachments'] as List<dynamic>? ?? const [])
                      .map((e) => e as Map<String, dynamic>)
                      .toList();

              return Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.88),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: AppColors.ink.withValues(alpha: 0.12),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 16,
                          backgroundColor: AppColors.ink,
                          backgroundImage:
                              reviewerAvatar != null &&
                                  reviewerAvatar.isNotEmpty
                              ? NetworkImage(reviewerAvatar)
                              : null,
                          child:
                              (reviewerAvatar == null || reviewerAvatar.isEmpty)
                              ? const Icon(
                                  Icons.person,
                                  color: Colors.white,
                                  size: 16,
                                )
                              : null,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            reviewerNickname,
                            style: TextStyle(
                              fontFamily: AppTypography.headerFont(locale),
                              fontSize: 17,
                              color: AppColors.ink,
                            ),
                          ),
                        ),
                        Text(
                          createdAt,
                          style: TextStyle(
                            fontFamily: AppTypography.bodyFont(locale),
                            fontSize: 12,
                            color: AppColors.ink.withValues(alpha: 0.65),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: List.generate(5, (index) {
                        final active = index < rating;
                        return Icon(
                          active ? Icons.star : Icons.star_border,
                          color: Colors.amber,
                          size: 18,
                        );
                      }),
                    ),
                    if (body != null && body.trim().isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        body,
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                          color: AppColors.ink,
                        ),
                      ),
                    ],
                    if (attachments.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: attachments.map((attachment) {
                          final imageUrl = attachment['file_url']?.toString();
                          if (imageUrl == null || imageUrl.isEmpty) {
                            return const SizedBox.shrink();
                          }
                          return InkWell(
                            onTap: () {
                              showDialog<void>(
                                context: context,
                                builder: (_) => Dialog(
                                  child: InteractiveViewer(
                                    child: Image.network(
                                      imageUrl,
                                      fit: BoxFit.contain,
                                    ),
                                  ),
                                ),
                              );
                            },
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: Image.network(
                                imageUrl,
                                width: 88,
                                height: 88,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => Container(
                                  width: 88,
                                  height: 88,
                                  color: Colors.black12,
                                  alignment: Alignment.center,
                                  child: const Icon(Icons.broken_image),
                                ),
                              ),
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  String _formatDate(String raw) {
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return raw;
    final day = parsed.day.toString().padLeft(2, '0');
    final month = parsed.month.toString().padLeft(2, '0');
    final year = parsed.year.toString();
    return '$day.$month.$year';
  }
}

class _CollectionsBlock extends StatelessWidget {
  const _CollectionsBlock({
    required this.title,
    required this.collections,
    required this.isRu,
    required this.isOwner,
    required this.onCreateCollection,
    required this.onDeleteCollection,
  });

  final String title;
  final List<Map<String, dynamic>> collections;
  final bool isRu;
  final bool isOwner;
  final VoidCallback onCreateCollection;
  final ValueChanged<String> onDeleteCollection;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontFamily: AppTypography.headerFont(locale),
                    fontSize: 22,
                  ),
                ),
              ),
              if (isOwner)
                IconButton(
                  onPressed: onCreateCollection,
                  icon: const Icon(
                    Icons.add_circle_outline,
                    color: AppColors.accent,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (collections.isEmpty)
            Text(
              isRu
                  ? 'Здесь пока ничего нет'
                  : 'Nothing here yet',
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                color: AppColors.ink.withOpacity(0.75),
              ),
            )
          else
            ...collections.map(
              (item) => _CollectionTile(
                item: item,
                isRu: isRu,
                isOwner: isOwner,
                onDelete: onDeleteCollection,
              ),
            ),
        ],
      ),
    );
  }
}

class _CollectionTile extends StatelessWidget {
  const _CollectionTile({
    required this.item,
    required this.isRu,
    required this.isOwner,
    required this.onDelete,
  });

  final Map<String, dynamic> item;
  final bool isRu;
  final bool isOwner;
  final ValueChanged<String> onDelete;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final previewUrl = item['preview_url']?.toString();

    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: () => Navigator.pushNamed(
        context,
        CollectionScreen.route,
        arguments: CollectionScreenArgs(
          collectionId: item['id'].toString(),
          isOwner: isOwner,
        ),
      ),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                width: 68,
                height: 68,
                child: previewUrl != null && previewUrl.isNotEmpty
                    ? Image.network(
                        previewUrl,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) =>
                            const ColoredBox(color: AppColors.ink),
                      )
                    : const ColoredBox(color: AppColors.ink),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _valueOrEmpty(item['title']?.toString(), isRu),
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    _valueOrEmpty(item['description']?.toString(), isRu),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: AppColors.ink.withOpacity(0.7),
                    ),
                  ),
                ],
              ),
            ),
            if (isOwner && (item['is_system'] ?? false) != true)
              IconButton(
                onPressed: () => onDelete(item['id'].toString()),
                icon: const Icon(Icons.delete_outline, color: AppColors.accent),
              )
            else
              const Icon(Icons.chevron_right, color: AppColors.ink),
          ],
        ),
      ),
    );
  }
}

class _StatBadge extends StatelessWidget {
  const _StatBadge({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.ink,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$label: $value',
        style: TextStyle(
          fontFamily: AppTypography.bodyFont(locale),
          color: Colors.white,
          fontSize: 12,
        ),
      ),
    );
  }
}

String _valueOrEmpty(String? value, bool isRu) {
  if (value == null || value.trim().isEmpty) {
    return isRu
        ? 'Здесь пока ничего нет'
        : 'Nothing here yet';
  }
  return value;
}
