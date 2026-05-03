import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'location_picker_screen.dart';
import 'profile_screen.dart';

class MastersFeedScreen extends StatefulWidget {
  const MastersFeedScreen({super.key});

  static const route = '/masters-feed';

  @override
  State<MastersFeedScreen> createState() => _MastersFeedScreenState();
}

class _MastersFeedScreenState extends State<MastersFeedScreen> {
  final _api = ApiClient.defaultClient();
  final _scrollController = ScrollController();
  final _searchController = TextEditingController();

  static const _pageSize = 20;

  List<Map<String, dynamic>> _masters = const [];
  List<Map<String, dynamic>> _styles = const [];
  List<Map<String, dynamic>> _tags = const [];

  bool _loadingInitial = true;
  bool _loadingMore = false;
  bool _hasMore = true;
  String? _error;
  int _offset = 0;

  Set<String> _styleIds = <String>{};
  Set<String> _tagIds = <String>{};
  double? _minRating;
  int? _maxPrice;
  bool _verifiedOnly = false;
  bool _favoriteOnly = false;
  LocationPickerResult? _cityLocation;
  int? _radiusMeters;
  String _sort = 'rating_desc';
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
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _boot() async {
    await _loadFilters();
    await _reload();
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
      if (stylesRes.statusCode == 200) {
        _styles = (jsonDecode(stylesRes.body) as List<dynamic>)
            .cast<Map<String, dynamic>>();
      }
      if (tagsRes.statusCode == 200) {
        _tags = (jsonDecode(tagsRes.body) as List<dynamic>)
            .cast<Map<String, dynamic>>();
      }
    } catch (_) {
      // non-blocking
    }
  }

  Future<void> _reload() async {
    setState(() {
      _loadingInitial = true;
      _error = null;
      _offset = 0;
      _hasMore = true;
      _masters = const [];
    });
    await _loadNext();
    if (!mounted) return;
    setState(() => _loadingInitial = false);
  }

  Future<void> _loadNext() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final query = <String, String>{
        'limit': _pageSize.toString(),
        'offset': _offset.toString(),
        'sort': _sort,
        if (_query.isNotEmpty) 'q': _query,
        if (_styleIds.isNotEmpty) 'style_ids': _styleIds.join(','),
        if (_tagIds.isNotEmpty) 'tag_ids': _tagIds.join(','),
        if (_minRating != null) 'min_rating': _minRating!.toStringAsFixed(1),
        if (_maxPrice != null) 'max_price': _maxPrice.toString(),
        if (_cityLocation != null) 'city_location_id': _cityLocation!.id,
        if (_cityLocation?.lat != null)
          'center_lat': _cityLocation!.lat!.toString(),
        if (_cityLocation?.lon != null)
          'center_lon': _cityLocation!.lon!.toString(),
        if (_radiusMeters != null) 'radius_meters': _radiusMeters.toString(),
        if (_verifiedOnly) 'verified_only': 'true',
        if (_favoriteOnly) 'favorite_only': 'true',
      };

      final res = await _api.getJson(
        '/profiles/masters',
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
        _masters = [..._masters, ...items];
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

  void _onScroll() {
    if (!_scrollController.hasClients ||
        _loadingMore ||
        _loadingInitial ||
        !_hasMore) {
      return;
    }
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 260) {
      _loadNext();
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 450), () {
      if (!mounted) return;
      setState(() => _query = value.trim());
      _reload();
    });
  }

  Future<void> _toggleSubscribe(Map<String, dynamic> master) async {
    final userId = master['user_id'].toString();
    final isSubscribed = (master['is_subscribed'] ?? false) == true;
    final res = isSubscribed
        ? await _api.deleteJson(
            '/subscriptions/$userId',
            accessToken: AppSession.instance.accessToken,
          )
        : await _api.postJson(
            '/subscriptions/$userId',
            {},
            accessToken: AppSession.instance.accessToken,
          );

    if (res.statusCode != 204 || !mounted) return;

    setState(() {
      _masters = _masters.map((item) {
        if (item['user_id'].toString() != userId) return item;
        final followers = (item['followers_count'] as num?)?.toInt() ?? 0;
        return {
          ...item,
          'is_subscribed': !isSubscribed,
          'followers_count': !isSubscribed
              ? followers + 1
              : (followers > 0 ? followers - 1 : 0),
        };
      }).toList();
    });
  }

  Future<void> _openFilters() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final style = Set<String>.from(_styleIds);
    final tag = Set<String>.from(_tagIds);
    var rating = _minRating;
    var verified = _verifiedOnly;
    var city = _cityLocation;
    final priceController = TextEditingController(
      text: _maxPrice?.toString() ?? '',
    );
    final radiusController = TextEditingController(
      text: _radiusMeters?.toString() ?? '',
    );

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _MasterFiltersSheet(
        isRu: isRu,
        styles: _styles,
        tags: _tags,
        styleIds: style,
        tagIds: tag,
        minRating: rating,
        verifiedOnly: verified,
        cityLocation: city,
        priceController: priceController,
        radiusController: radiusController,
        onPickCity: () async {
          final result = await Navigator.push<LocationPickerResult>(
            context,
            MaterialPageRoute(
              builder: (_) => LocationPickerScreen(
                title: isRu ? 'Город мастеров' : 'Masters city',
                precisionLevel: 'locality',
              ),
            ),
          );
          if (result != null) {
            city = result;
          }
          return city;
        },
        onApply: (newRating, newVerified) {
          setState(() {
            _styleIds = style;
            _tagIds = tag;
            _minRating = newRating;
            _verifiedOnly = newVerified;
            _maxPrice = int.tryParse(priceController.text.trim());
            _cityLocation = city;
            _radiusMeters = int.tryParse(radiusController.text.trim());
          });
          Navigator.pop(context);
          _reload();
        },
        onReset: () {
          setState(() {
            _styleIds.clear();
            _tagIds.clear();
            _minRating = null;
            _maxPrice = null;
            _verifiedOnly = false;
            _cityLocation = null;
            _radiusMeters = null;
          });
          Navigator.pop(context);
          _reload();
        },
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
        title: Text(isRu ? 'Лента мастеров' : 'Master feed'),
        leading: IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back),
        ),
        actions: [
          IconButton(onPressed: _openFilters, icon: const Icon(Icons.tune)),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: isRu ? 'Поиск мастеров' : 'Search masters',
                prefixIcon: const Icon(Icons.search),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  avatar: const Icon(Icons.verified, size: 18),
                  label: Text(isRu ? 'Проверенные' : 'Verified'),
                  selected: _verifiedOnly,
                  onSelected: (value) {
                    setState(() => _verifiedOnly = value);
                    _reload();
                  },
                ),
                FilterChip(
                  avatar: Icon(
                    Icons.star,
                    size: 18,
                    color: _favoriteOnly ? Colors.white : Colors.amber,
                  ),
                  label: Text(
                    isRu ? 'Фавориты InkMatch' : 'InkMatch favorites',
                  ),
                  selected: _favoriteOnly,
                  onSelected: (value) {
                    setState(() => _favoriteOnly = value);
                    _reload();
                  },
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: DropdownButtonFormField<String>(
              initialValue: _sort,
              items:
                  [
                        ('rating_desc', isRu ? 'Рейтинг ↓' : 'Rating ↓'),
                        (
                          'followers_desc',
                          isRu ? 'Подписчики ↓' : 'Followers ↓',
                        ),
                        ('works_desc', isRu ? 'Работы ↓' : 'Works ↓'),
                        ('price_asc', isRu ? 'Цена ↑' : 'Price ↑'),
                        ('newest', isRu ? 'Новые' : 'Newest'),
                      ]
                      .map(
                        (item) => DropdownMenuItem(
                          value: item.$1,
                          child: Text(item.$2),
                        ),
                      )
                      .toList(),
              onChanged: (value) {
                if (value == null || value == _sort) return;
                setState(() => _sort = value);
                _reload();
              },
            ),
          ),
          if (_loadingInitial)
            const Expanded(child: Center(child: CircularProgressIndicator()))
          else if (_error != null && _masters.isEmpty)
            Expanded(child: Center(child: Text(_error!)))
          else
            Expanded(
              child: RefreshIndicator(
                onRefresh: _reload,
                child: ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
                  itemCount: _masters.length + (_loadingMore ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index >= _masters.length) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 16),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    return _MasterTile(
                      master: _masters[index],
                      isRu: isRu,
                      onToggleSubscribe: () =>
                          _toggleSubscribe(_masters[index]),
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

class _MasterTile extends StatelessWidget {
  const _MasterTile({
    required this.master,
    required this.isRu,
    required this.onToggleSubscribe,
  });

  final Map<String, dynamic> master;
  final bool isRu;
  final VoidCallback onToggleSubscribe;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final preview = master['preview_image_url']?.toString();
    final avatar = master['avatar_url']?.toString();
    final subscribed = (master['is_subscribed'] ?? false) == true;
    final favorite = (master['is_favorite'] ?? false) == true;

    return InkWell(
      onTap: () => Navigator.pushNamed(
        context,
        ProfileScreen.route,
        arguments: ProfileScreenArgs(userId: master['user_id'].toString()),
      ),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox(
                width: 86,
                height: 86,
                child: preview == null || preview.isEmpty
                    ? Container(color: AppColors.ink.withValues(alpha: 0.14))
                    : Image.network(
                        preview,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => Container(
                          color: AppColors.ink.withValues(alpha: 0.14),
                        ),
                      ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        radius: 14,
                        backgroundImage: avatar != null && avatar.isNotEmpty
                            ? NetworkImage(avatar)
                            : null,
                        child: avatar == null || avatar.isEmpty
                            ? const Icon(Icons.person, size: 14)
                            : null,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          master['nickname']?.toString() ?? 'master',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontFamily: AppTypography.headerFont(locale),
                            fontSize: 18,
                          ),
                        ),
                      ),
                      if (favorite) ...[
                        const SizedBox(width: 4),
                        const Icon(Icons.star, color: Colors.amber, size: 18),
                      ],
                    ],
                  ),
                  const SizedBox(height: 6),
                  if (favorite)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text(
                        isRu ? 'Фаворит InkMatch' : 'InkMatch favorite',
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: Colors.amber.shade800,
                        ),
                      ),
                    ),
                  Text(
                    '★ ${(master['master_rating'] as num?)?.toStringAsFixed(1) ?? '0.0'} · ${(master['followers_count'] as num?)?.toInt() ?? 0} ${isRu ? 'подписчиков' : 'followers'}',
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    master['master_address']?.toString() ??
                        (isRu ? 'Адрес не указан' : 'Address not specified'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      fontSize: 12,
                      color: AppColors.ink.withValues(alpha: 0.7),
                    ),
                  ),
                  const SizedBox(height: 8),
                  ElevatedButton(
                    onPressed: onToggleSubscribe,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: subscribed
                          ? AppColors.ink
                          : AppColors.accent,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(120, 32),
                      padding: EdgeInsets.zero,
                    ),
                    child: Text(
                      subscribed
                          ? (isRu ? 'Вы подписаны' : 'Following')
                          : (isRu ? 'Подписаться' : 'Follow'),
                      style: TextStyle(
                        fontFamily: AppTypography.bodyFont(locale),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MasterFiltersSheet extends StatefulWidget {
  const _MasterFiltersSheet({
    required this.isRu,
    required this.styles,
    required this.tags,
    required this.styleIds,
    required this.tagIds,
    required this.minRating,
    required this.verifiedOnly,
    required this.cityLocation,
    required this.priceController,
    required this.radiusController,
    required this.onPickCity,
    required this.onApply,
    required this.onReset,
  });

  final bool isRu;
  final List<Map<String, dynamic>> styles;
  final List<Map<String, dynamic>> tags;
  final Set<String> styleIds;
  final Set<String> tagIds;
  final double? minRating;
  final bool verifiedOnly;
  final LocationPickerResult? cityLocation;
  final TextEditingController priceController;
  final TextEditingController radiusController;
  final Future<LocationPickerResult?> Function() onPickCity;
  final void Function(double?, bool) onApply;
  final VoidCallback onReset;

  @override
  State<_MasterFiltersSheet> createState() => _MasterFiltersSheetState();
}

class _MasterFiltersSheetState extends State<_MasterFiltersSheet> {
  late double? _rating = widget.minRating;
  late bool _verifiedOnly = widget.verifiedOnly;
  late LocationPickerResult? _cityLocation = widget.cityLocation;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 16,
            bottom: MediaQuery.of(context).viewInsets.bottom + 16,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(widget.isRu ? 'Фильтры мастеров' : 'Master filters'),
              Slider(
                value: _rating ?? 0,
                min: 0,
                max: 5,
                divisions: 10,
                onChanged: (v) => setState(() => _rating = v == 0 ? null : v),
              ),
              TextField(
                controller: widget.priceController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: widget.isRu ? 'Макс. цена' : 'Max price',
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  final result = await widget.onPickCity();
                  if (result != null) {
                    setState(() => _cityLocation = result);
                  }
                },
                icon: const Icon(Icons.place),
                label: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    _cityLocation?.label ??
                        (widget.isRu
                            ? 'Город / центр радиуса'
                            : 'City / radius center'),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: widget.radiusController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: widget.isRu ? 'Радиус (м)' : 'Radius (m)',
                ),
              ),
              SwitchListTile(
                value: _verifiedOnly,
                contentPadding: EdgeInsets.zero,
                onChanged: (v) => setState(() => _verifiedOnly = v),
                title: Text(
                  widget.isRu ? 'Только проверенные' : 'Verified only',
                ),
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: widget.styles.map((e) {
                  final id = e['id'].toString();
                  return FilterChip(
                    label: Text(e['name']?.toString() ?? ''),
                    selected: widget.styleIds.contains(id),
                    onSelected: (v) => setState(
                      () => v
                          ? widget.styleIds.add(id)
                          : widget.styleIds.remove(id),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: widget.tags.map((e) {
                  final id = e['id'].toString();
                  return FilterChip(
                    label: Text(e['name']?.toString() ?? ''),
                    selected: widget.tagIds.contains(id),
                    onSelected: (v) => setState(
                      () =>
                          v ? widget.tagIds.add(id) : widget.tagIds.remove(id),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: widget.onReset,
                      child: Text(widget.isRu ? 'Сбросить' : 'Reset'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => widget.onApply(_rating, _verifiedOnly),
                      child: Text(widget.isRu ? 'Применить' : 'Apply'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
