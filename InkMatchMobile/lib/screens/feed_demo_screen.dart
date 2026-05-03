import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_staggered_grid_view/flutter_staggered_grid_view.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../services/media_url_helper.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'chat_list_screen.dart';
import 'notifications_screen.dart';
import 'post_demo_screen.dart';
import 'profile_screen.dart';
import 'artists_feed_screen.dart';
import 'create_post_screen.dart';

class FeedDemoScreen extends StatefulWidget {
  const FeedDemoScreen({super.key});

  static const route = '/demo-feed';

  @override
  State<FeedDemoScreen> createState() => _FeedDemoScreenState();
}

class _FeedDemoScreenState extends State<FeedDemoScreen> {
  final _api = ApiClient.defaultClient();
  final _scrollController = ScrollController();
  final _searchController = TextEditingController();

  static const _pageSize = 20;

  bool _loadingInitial = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  String? _error;

  int _offset = 0;
  int _unreadNotifications = 0;
  List<Map<String, dynamic>> _posts = const [];

  List<Map<String, dynamic>> _styles = const [];
  List<Map<String, dynamic>> _tags = const [];
  Set<String> _selectedStyleIds = <String>{};
  Set<String> _selectedTagIds = <String>{};
  String _query = '';
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _boot();
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _boot() async {
    await _loadFilters();
    await _reloadFeed();
    await _loadUnreadCount();
  }

  Future<void> _loadFilters() async {
    try {
      final stylesRes = await _api.getJson(
        '/catalogs/styles',
        accessToken: AppSession.instance.accessToken,
      );
      final tagsRes = await _api.getJson(
        '/catalogs/tags',
        accessToken: AppSession.instance.accessToken,
      );

      final styles = stylesRes.statusCode == 200
          ? (jsonDecode(stylesRes.body) as List<dynamic>)
                .cast<Map<String, dynamic>>()
          : const <Map<String, dynamic>>[];
      final tags = tagsRes.statusCode == 200
          ? (jsonDecode(tagsRes.body) as List<dynamic>)
                .cast<Map<String, dynamic>>()
          : const <Map<String, dynamic>>[];

      if (!mounted) return;
      setState(() {
        _styles = styles;
        _tags = tags;
      });
    } catch (_) {
      // non-blocking
    }
  }

  Future<void> _loadUnreadCount() async {
    try {
      final res = await _api.getJson(
        '/notifications/unread-count',
        accessToken: AppSession.instance.accessToken,
      );
      if (!mounted || res.statusCode != 200) {
        return;
      }
      final payload = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _unreadNotifications = (payload['count'] as num?)?.toInt() ?? 0;
      });
    } catch (_) {
      // non-blocking
    }
  }

  Future<void> _reloadFeed() async {
    if (!mounted) return;
    setState(() {
      _loadingInitial = true;
      _error = null;
      _offset = 0;
      _hasMore = true;
      _posts = const [];
    });
    await _loadNextPage();
    if (!mounted) return;
    setState(() => _loadingInitial = false);
  }

  void _onScroll() {
    if (!_scrollController.hasClients ||
        _loadingMore ||
        !_hasMore ||
        _loadingInitial) {
      return;
    }
    final threshold = _scrollController.position.maxScrollExtent - 300;
    if (_scrollController.position.pixels >= threshold) {
      _loadNextPage();
    }
  }

  Future<void> _loadNextPage() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);

    try {
      final query = <String, String>{
        'limit': _pageSize.toString(),
        'offset': _offset.toString(),
        if (_selectedStyleIds.isNotEmpty)
          'style_ids': _selectedStyleIds.join(','),
        if (_selectedTagIds.isNotEmpty) 'tag_ids': _selectedTagIds.join(','),
        if (_query.isNotEmpty) 'q': _query,
      };

      final res = await _api.getJson(
        '/posts/feed',
        accessToken: AppSession.instance.accessToken,
        query: query,
      );
      if (res.statusCode != 200) {
        if (!mounted) return;
        setState(() => _error = '${res.statusCode}: ${res.body}');
        return;
      }

      final items = (jsonDecode(res.body) as List<dynamic>)
          .cast<Map<String, dynamic>>();
      if (!mounted) return;
      setState(() {
        _posts = [..._posts, ...items];
        _offset += items.length;
        _hasMore = items.length == _pageSize;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      setState(() => _query = value.trim());
      _reloadFeed();
    });
  }

  List<Map<String, dynamic>> _filteredCatalogItems(
    List<Map<String, dynamic>> items,
    String query,
  ) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return items;
    return items.where((item) {
      final name = item['name']?.toString().toLowerCase() ?? '';
      return name.contains(q);
    }).toList();
  }

  Future<void> _openCatalogPicker({
    required String titleRu,
    required String titleEn,
    required List<Map<String, dynamic>> items,
    required Set<String> selectedIds,
    required bool isRu,
    required Color selectedColor,
    required void Function(Set<String>) onApply,
  }) async {
    final queryCtrl = TextEditingController();
    final localSelected = Set<String>.from(selectedIds);
    var query = '';

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final filtered = _filteredCatalogItems(items, query);
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  16,
                  16,
                  16,
                  16 + MediaQuery.of(context).viewInsets.bottom,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isRu ? titleRu : titleEn,
                      style: TextStyle(
                        fontFamily: AppTypography.headerFont(
                          AppLocaleScope.of(context).locale,
                        ),
                        fontSize: 20,
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: queryCtrl,
                      onChanged: (v) => setSheetState(() => query = v),
                      decoration: InputDecoration(
                        prefixIcon: const Icon(Icons.search),
                        hintText: isRu ? 'Поиск' : 'Search',
                      ),
                    ),
                    const SizedBox(height: 12),
                    Flexible(
                      child: SingleChildScrollView(
                        child: Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: filtered.map((item) {
                            final id = item['id'].toString();
                            final selected = localSelected.contains(id);
                            return FilterChip(
                              selected: selected,
                              selectedColor: selectedColor,
                              showCheckmark: true,
                              checkmarkColor: Colors.white,
                              labelStyle: TextStyle(
                                color: selected ? Colors.white : AppColors.ink,
                                fontFamily: AppTypography.bodyFont(
                                  AppLocaleScope.of(context).locale,
                                ),
                              ),
                              label: Text(item['name']?.toString() ?? ''),
                              onSelected: (v) => setSheetState(() {
                                if (v) {
                                  localSelected.add(id);
                                } else {
                                  localSelected.remove(id);
                                }
                              }),
                            );
                          }).toList(),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () {
                              localSelected.clear();
                              setSheetState(() {});
                            },
                            child: Text(isRu ? 'Сбросить' : 'Reset'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: ElevatedButton(
                            onPressed: () {
                              onApply(localSelected);
                              Navigator.pop(context);
                            },
                            child: Text(isRu ? 'Применить' : 'Apply'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _openFilters() async {
    final localStyle = Set<String>.from(_selectedStyleIds);
    final localTag = Set<String>.from(_selectedTagIds);
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return SafeArea(
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(context).size.height * 0.82,
                ),
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isRu
                            ? 'Фильтры ленты'
                            : 'Feed filters',
                        style: TextStyle(
                          fontFamily: AppTypography.headerFont(locale),
                          fontSize: 24,
                        ),
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            Navigator.pop(context);
                            _openCatalogPicker(
                              titleRu: 'Выберите стили',
                              titleEn: 'Pick styles',
                              items: _styles,
                              selectedIds: localStyle,
                              isRu: isRu,
                              selectedColor: AppColors.accent,
                              onApply: (selected) {
                                setState(() => _selectedStyleIds = selected);
                                _reloadFeed();
                              },
                            );
                          },
                          icon: const Icon(Icons.style_outlined),
                          label: Text(
                            isRu
                                ? 'Стили (${localStyle.length})'
                                : 'Styles (${localStyle.length})',
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            Navigator.pop(context);
                            _openCatalogPicker(
                              titleRu: 'Выберите теги',
                              titleEn: 'Pick tags',
                              items: _tags,
                              selectedIds: localTag,
                              isRu: isRu,
                              selectedColor: AppColors.ink,
                              onApply: (selected) {
                                setState(() => _selectedTagIds = selected);
                                _reloadFeed();
                              },
                            );
                          },
                          icon: const Icon(Icons.label_outlined),
                          label: Text(
                            isRu
                                ? 'Теги (${localTag.length})'
                                : 'Tags (${localTag.length})',
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () {
                                setState(() {
                                  _selectedStyleIds.clear();
                                  _selectedTagIds.clear();
                                });
                                Navigator.pop(context);
                                _reloadFeed();
                              },
                              child: Text(
                                isRu
                                    ? 'Сбросить'
                                    : 'Reset',
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.accent,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: () {
                                setState(() {
                                  _selectedStyleIds = localStyle;
                                  _selectedTagIds = localTag;
                                });
                                Navigator.pop(context);
                                _reloadFeed();
                              },
                              child: Text(
                                isRu
                                    ? 'Применить'
                                    : 'Apply',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 10),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () =>
                          Navigator.pushNamed(context, MastersFeedScreen.route),
                      icon: const Icon(Icons.people_outline),
                      label: Text(
                        isRu
                            ? 'Лента мастеров'
                            : 'Master feed',
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                children: [
                  Expanded(
                    child: _SearchBar(
                      hint: isRu
                          ? 'Поиск по эскизам, авторам и описанию'
                          : 'Search posts, authors and descriptions',
                      controller: _searchController,
                      onChanged: _onSearchChanged,
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    onPressed: _openFilters,
                    style: IconButton.styleFrom(
                      backgroundColor: AppColors.ink,
                      foregroundColor: Colors.white,
                    ),
                    icon: const Icon(Icons.tune),
                  ),
                ],
              ),
            ),
            if (_selectedStyleIds.isNotEmpty || _selectedTagIds.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 6, 14, 0),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    isRu
                        ? 'Фильтры: стилей ${_selectedStyleIds.length}, тегов ${_selectedTagIds.length}'
                        : 'Filters: styles ${_selectedStyleIds.length}, tags ${_selectedTagIds.length}',
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: AppColors.ink.withValues(alpha: 0.85),
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 8),
            if (_loadingInitial)
              const Expanded(child: Center(child: CircularProgressIndicator()))
            else if (_error != null && _posts.isEmpty)
              Expanded(child: Center(child: Text(_error!)))
            else
              Expanded(
                child: RefreshIndicator(
                  onRefresh: _reloadFeed,
                  child: MasonryGridView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(10, 12, 10, 10),
                    gridDelegate:
                        const SliverSimpleGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                        ),
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                    itemCount: _posts.length + (_loadingMore ? 2 : 0),
                    itemBuilder: (context, index) {
                      if (index >= _posts.length) {
                        return Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(14),
                            color: AppColors.ink.withValues(alpha: 0.08),
                          ),
                          child: const Center(
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        );
                      }
                      return _FeedCard(post: _posts[index]);
                    },
                  ),
                ),
              ),
            _BottomNavBar(
              unreadNotifications: _unreadNotifications,
              onOpenNotifications: () async {
                await Navigator.pushNamed(context, NotificationsScreen.route);
                await _loadUnreadCount();
              },
              onCreatePost: () async {
                final created = await Navigator.pushNamed(
                  context,
                  CreatePostScreen.route,
                );
                if (created == true) {
                  await _reloadFeed();
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _FeedCard extends StatelessWidget {
  const _FeedCard({required this.post});

  final Map<String, dynamic> post;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final imageUrl = MediaUrlHelper.resolveUrl(post['image_url']?.toString());

    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () => Navigator.pushNamed(
        context,
        PostDemoScreen.route,
        arguments: post['id']?.toString(),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: SizedBox(
              width: double.infinity,
              child: _FeedThumbnail(
                postId: post['id']?.toString() ?? '',
                initialUrl: imageUrl,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            post['author_nickname']?.toString() ?? 'user',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink,
              fontWeight: FontWeight.w700,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}

class _FeedThumbnail extends StatefulWidget {
  const _FeedThumbnail({
    required this.postId,
    required this.initialUrl,
  });

  final String postId;
  final String? initialUrl;

  @override
  State<_FeedThumbnail> createState() => _FeedThumbnailState();
}

class _FeedThumbnailState extends State<_FeedThumbnail> {
  final _api = ApiClient.defaultClient();
  String? _url;
  bool _retrying = false;
  bool _retriedOnce = false;

  @override
  void initState() {
    super.initState();
    _url = widget.initialUrl;
  }

  Future<void> _retryWithFreshUrl() async {
    if (_retrying || widget.postId.isEmpty) return;
    _retrying = true;
    try {
      final res = await _api.getJson(
        '/posts/${widget.postId}',
        accessToken: AppSession.instance.accessToken,
      );
      if (res.statusCode != 200 || !mounted) return;
      final payload = jsonDecode(res.body) as Map<String, dynamic>;
      final media = (payload['media_urls'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .where((e) => e.isNotEmpty)
          .toList();
      final fresh = MediaUrlHelper.resolveUrl(media.isNotEmpty ? media.first : null);
      if (fresh != null && fresh.isNotEmpty) {
        setState(() => _url = fresh);
      }
    } catch (_) {
      // keep the fallback
    } finally {
      _retrying = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final url = _url;
    return AspectRatio(
      aspectRatio: 0.82,
      child: url == null || url.isEmpty
          ? Container(
              color: AppColors.ink,
              child: const Center(
                child: Icon(Icons.image_not_supported, color: Colors.white),
              ),
            )
          : Image.network(
              url,
              width: double.infinity,
              fit: BoxFit.cover,
              gaplessPlayback: true,
              loadingBuilder: (context, child, loadingProgress) {
                if (loadingProgress == null) return child;
                return Container(
                  color: AppColors.ink.withValues(alpha: 0.08),
                  alignment: Alignment.center,
                  child: const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                );
              },
              errorBuilder: (_, __, ___) {
                if (!_retrying && !_retriedOnce) {
                  _retriedOnce = true;
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    _retryWithFreshUrl();
                  });
                }
                return Container(
                  color: AppColors.ink,
                  child: const Center(
                    child: Icon(Icons.broken_image, color: Colors.white),
                  ),
                );
              },
            ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar({
    required this.hint,
    required this.controller,
    required this.onChanged,
  });

  final String hint;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return TextField(
      controller: controller,
      onChanged: onChanged,
      style: TextStyle(
        fontFamily: AppTypography.bodyFont(locale),
        color: AppColors.ink,
      ),
      decoration: InputDecoration(
        hintText: hint,
        prefixIcon: const Icon(Icons.search, color: AppColors.ink),
        contentPadding: const EdgeInsets.symmetric(vertical: 10),
      ),
    );
  }
}

class _BottomNavBar extends StatelessWidget {
  const _BottomNavBar({
    required this.unreadNotifications,
    required this.onOpenNotifications,
    required this.onCreatePost,
  });

  final int unreadNotifications;
  final VoidCallback onOpenNotifications;
  final VoidCallback onCreatePost;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      color: AppColors.ink,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Icon(Icons.home_filled, color: Colors.white, size: 30),
          Stack(
            clipBehavior: Clip.none,
            children: [
              IconButton(
                onPressed: onOpenNotifications,
                icon: const Icon(
                  Icons.notifications_none,
                  color: Colors.white,
                  size: 28,
                ),
              ),
              if (unreadNotifications > 0)
                Positioned(
                  right: 2,
                  top: 2,
                  child: Container(
                    width: 16,
                    height: 16,
                    decoration: const BoxDecoration(
                      color: AppColors.accent,
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      unreadNotifications > 9 ? '9+' : '$unreadNotifications',
                      style: const TextStyle(color: Colors.white, fontSize: 9),
                    ),
                  ),
                ),
            ],
          ),
          IconButton(
            onPressed: onCreatePost,
            icon: const Icon(Icons.add, color: Colors.white, size: 32),
          ),
          IconButton(
            onPressed: () => Navigator.pushNamed(context, ChatListScreen.route),
            icon: const Icon(
              Icons.chat_bubble_outline,
              color: Colors.white,
              size: 28,
            ),
          ),
          IconButton(
            onPressed: () => Navigator.pushNamed(
              context,
              ProfileScreen.route,
              arguments: const ProfileScreenArgs(),
            ),
            icon: const Icon(
              Icons.person_outline,
              color: Colors.white,
              size: 29,
            ),
          ),
        ],
      ),
    );
  }
}
