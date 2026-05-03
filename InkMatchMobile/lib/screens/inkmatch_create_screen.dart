import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'location_picker_screen.dart';
import 'map_point_picker_screen.dart';

class InkmatchCreateScreenArgs {
  const InkmatchCreateScreenArgs({required this.sketchId});

  final String sketchId;
}

class InkmatchCreateScreen extends StatefulWidget {
  const InkmatchCreateScreen({super.key});

  static const route = '/inkmatch-create';

  @override
  State<InkmatchCreateScreen> createState() => _InkmatchCreateScreenState();
}

class _InkmatchCreateScreenState extends State<InkmatchCreateScreen> {
  final _api = ApiClient.defaultClient();

  final _sizeCtrl = TextEditingController();
  final _radiusCtrl = TextEditingController();
  final _offerPriceCtrl = TextEditingController();
  final _offerDurationCtrl = TextEditingController(text: '120');

  bool _loading = true;
  bool _saving = false;
  bool _saveDefaults = false;
  String? _error;

  String _searchMode = 'city';
  String _workplace = 'any';
  RangeValues _budget = const RangeValues(3000, 15000);
  double _expMin = 0;
  int _ratingMin = 0;
  LocationPickerResult? _cityLocation;
  LocationPickerResult? _regionLocation;
  MapPointPickerResult? _radiusArea;

  String get _token => AppSession.instance.accessToken ?? '';
  bool get _isMaster => AppSession.instance.role == SessionUserRole.master;

  String _t(bool isRu, String ru, String en) => isRu ? ru : en;

  String get _sketchId {
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is InkmatchCreateScreenArgs) return args.sketchId;
    return '';
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadDefaults());
  }

  @override
  void dispose() {
    _sizeCtrl.dispose();
    _radiusCtrl.dispose();
    _offerPriceCtrl.dispose();
    _offerDurationCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadDefaults() async {
    if (_token.isEmpty) {
      setState(() {
        _loading = false;
        _error =
            'Пользователь не авторизован';
      });
      return;
    }

    if (_isMaster) {
      setState(() => _loading = false);
      return;
    }

    try {
      final res = await _api.getJson(
        '/account/inkmatch-defaults',
        accessToken: _token,
      );
      if (!mounted) return;

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        _sizeCtrl.text = (data['default_size_sm'] ?? '').toString();
        _radiusCtrl.text = (data['radius_meters'] ?? '').toString();

        final min = ((data['default_price_min'] as num?) ?? 3000).toDouble();
        final max = ((data['default_price_max'] as num?) ?? 15000).toDouble();
        _budget = RangeValues(min.clamp(0, 300000), max.clamp(0, 300000));
        if (_budget.start > _budget.end) {
          _budget = RangeValues(_budget.end, _budget.start);
        }

        _expMin = (((data['experience_years_min'] as num?) ?? 0).toDouble())
            .clamp(0, 10);
        _ratingMin = (((data['rating_min'] as num?) ?? 0).round()).clamp(0, 5);

        final searchMode = data['search_mode']?.toString();
        if (searchMode != null &&
            {'city', 'region', 'radius'}.contains(searchMode)) {
          _searchMode = searchMode;
        }

        final workplace = data['workplace']?.toString();
        if (workplace != null &&
            {'any', 'studio', 'home'}.contains(workplace)) {
          _workplace = workplace;
        }
        await _loadSavedLocation(data['city_location_id']?.toString(), true);
        await _loadSavedLocation(data['region_location_id']?.toString(), false);
        final centerLat = (data['center_lat'] as num?)?.toDouble();
        final centerLon = (data['center_lon'] as num?)?.toDouble();
        final radius = (data['radius_meters'] as num?)?.toInt();
        if (centerLat != null && centerLon != null) {
          _radiusArea = MapPointPickerResult(
            lat: centerLat,
            lon: centerLon,
            radiusMeters: radius,
          );
        }
      }

      setState(() => _loading = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  int? _toInt(TextEditingController ctrl) {
    final value = ctrl.text.trim();
    if (value.isEmpty) return null;
    return int.tryParse(value);
  }

  Future<void> _loadSavedLocation(String? id, bool city) async {
    if (id == null || id.isEmpty || id == 'null') return;
    final res = await _api.getJson('/geo/locations/$id', accessToken: _token);
    if (res.statusCode != 200) return;
    final result = LocationPickerResult(
      Map<String, dynamic>.from(jsonDecode(res.body) as Map),
    );
    if (city) {
      _cityLocation = result;
    } else {
      _regionLocation = result;
    }
  }

  Future<void> _pickLocation(bool city) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<LocationPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => LocationPickerScreen(
          title: city
              ? _t(isRu, 'Город поиска', 'Search city')
              : _t(isRu, 'Регион поиска', 'Search region'),
          precisionLevel: 'locality',
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      if (city) {
        _cityLocation = result;
      } else {
        _regionLocation = result;
      }
    });
  }

  Future<void> _pickRadiusArea() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<MapPointPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => MapPointPickerScreen(
          title: _t(isRu, 'Радиус поиска', 'Search radius'),
          radiusEnabled: true,
          initialLat: _radiusArea?.lat ?? _cityLocation?.lat,
          initialLon: _radiusArea?.lon ?? _cityLocation?.lon,
          initialRadiusMeters: _radiusArea?.radiusMeters ?? _toInt(_radiusCtrl),
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      _radiusArea = result;
      _radiusCtrl.text = (result.radiusMeters ?? 5000).toString();
    });
  }

  Future<void> _submit() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    if (_saving) return;

    if (_sketchId.isEmpty) {
      setState(
        () => _error = _t(
          isRu,
          'Не найден ID эскиза',
          'Sketch id is missing',
        ),
      );
      return;
    }

    if (_isMaster) {
      final offerPrice = _toInt(_offerPriceCtrl);
      final duration = _toInt(_offerDurationCtrl);
      if (offerPrice == null ||
          offerPrice <= 0 ||
          duration == null ||
          duration < 10) {
        setState(
          () => _error = _t(
            isRu,
            'Заполните цену и длительность корректно',
            'Fill price and duration correctly',
          ),
        );
        return;
      }
    } else {
      if (_searchMode == 'city' && _cityLocation == null) {
        setState(() => _error = _t(isRu, 'Выберите город поиска', 'Choose search city'));
        return;
      }
      if (_searchMode == 'region' && _regionLocation == null) {
        setState(() => _error = _t(isRu, 'Выберите область поиска', 'Choose search region'));
        return;
      }
      if (_searchMode == 'radius' &&
          (_radiusArea == null || (_radiusArea?.radiusMeters ?? 0) <= 0)) {
        setState(() => _error = _t(isRu, 'Выберите центр и радиус поиска', 'Choose search center and radius'));
        return;
      }
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final createRes = await _api.postJson('/inkmatch/requests', {
        'sketch_id': _sketchId,
        'created_by_role': _isMaster ? 'master' : 'client',
      }, accessToken: _token);
      if (!mounted) return;

      if (createRes.statusCode != 201) {
        setState(() {
          _saving = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            createRes.statusCode,
            createRes.body,
            fallback: _t(
              isRu,
              'Не удалось создать заявку InkMatch',
              'Failed to create InkMatch request',
            ),
          );
        });
        return;
      }

      final request = jsonDecode(createRes.body) as Map<String, dynamic>;
      final requestId = request['id']?.toString() ?? '';

      if (_isMaster) {
        final offerRes = await _api
            .putJson('/inkmatch/requests/$requestId/offer', {
              'offer_price': _toInt(_offerPriceCtrl) ?? 0,
              'offer_duration_minutes': _toInt(_offerDurationCtrl) ?? 120,
            }, accessToken: _token);

        if (offerRes.statusCode != 200) {
          setState(() {
            _saving = false;
            _error = ApiErrorMapper.mapHttpError(
              context,
              offerRes.statusCode,
              offerRes.body,
              fallback: _t(
                isRu,
                'Не удалось сохранить параметры',
                'Failed to save master preferences',
              ),
            );
          });
          return;
        }
      } else {
        final paramsRes = await _api
            .putJson('/inkmatch/requests/$requestId/client-params', {
              'size_sm': _toInt(_sizeCtrl),
              'price_min': _budget.start.round(),
              'price_max': _budget.end.round(),
              'search_mode': _searchMode,
              'city_location_id': _cityLocation?.id,
              'region_location_id': _regionLocation?.id,
              'center_lat': _radiusArea?.lat ?? _cityLocation?.lat,
              'center_lon': _radiusArea?.lon ?? _cityLocation?.lon,
              'radius_meters': _radiusArea?.radiusMeters ?? _toInt(_radiusCtrl),
              'preferred_experience_years_min': _expMin.round(),
              'preferred_rating_min': _ratingMin.toDouble(),
              'preferred_workplace': _workplace,
            }, accessToken: _token);

        if (paramsRes.statusCode != 200) {
          setState(() {
            _saving = false;
            _error = ApiErrorMapper.mapHttpError(
              context,
              paramsRes.statusCode,
              paramsRes.body,
              fallback: _t(
                isRu,
                'Не удалось сохранить параметры',
                'Failed to save client preferences',
              ),
            );
          });
          return;
        }

        if (_saveDefaults) {
          final defaultsRes = await _api.putJson('/account/inkmatch-defaults', {
            'experience_years_min': _expMin.round(),
            'rating_min': _ratingMin.toDouble(),
            'workplace': _workplace,
            'search_mode': _searchMode,
            'city_location_id': _cityLocation?.id,
            'region_location_id': _regionLocation?.id,
            'center_lat': _radiusArea?.lat ?? _cityLocation?.lat,
            'center_lon': _radiusArea?.lon ?? _cityLocation?.lon,
            'radius_meters': _radiusArea?.radiusMeters ?? _toInt(_radiusCtrl),
            'default_size_sm': _toInt(_sizeCtrl),
            'default_price_min': _budget.start.round(),
            'default_price_max': _budget.end.round(),
          }, accessToken: _token);
          if (defaultsRes.statusCode != 200) {
            setState(() {
              _saving = false;
              _error = ApiErrorMapper.mapHttpError(
                context,
                defaultsRes.statusCode,
                defaultsRes.body,
                fallback: _t(
                  isRu,
                  'Не удалось сохранить предпочтения',
                  'Failed to save defaults',
                ),
              );
            });
            return;
          }
        }
      }

      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _t(
              isRu,
              'Заявка InkMatch создана',
              'InkMatch request created',
            ),
          ),
        ),
      );
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'InkMatch',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
        backgroundColor: AppColors.background,
      ),
      backgroundColor: AppColors.background,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_error != null)
                    Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: Colors.red),
                      ),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Colors.red.shade800,
                          fontFamily: AppTypography.bodyFont(locale),
                        ),
                      ),
                    ),
                  Text(
                    _isMaster
                        ? _t(
                            isRu,
                            'Параметры предложения мастера',
                            'Master offer',
                          )
                        : _t(
                            isRu,
                            'Параметры запроса клиента',
                            'Client request',
                          ),
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 22,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (_isMaster) ...[
                    _InkNumberField(
                      controller: _offerPriceCtrl,
                      label: _t(
                        isRu,
                        'Точная цена (₽)',
                        'Exact price',
                      ),
                    ),
                    const SizedBox(height: 8),
                    _LocationButton(
                      label: _t(isRu, 'Город', 'City'),
                      value: _cityLocation?.label,
                      onPressed: () => _pickLocation(true),
                    ),
                    const SizedBox(height: 8),
                    _LocationButton(
                      label: _t(isRu, 'Регион', 'Region'),
                      value: _regionLocation?.label,
                      onPressed: () => _pickLocation(false),
                    ),
                    const SizedBox(height: 8),
                    _InkNumberField(
                      controller: _offerDurationCtrl,
                      label: _t(
                        isRu,
                        'Длительность, минут',
                        'Duration, min',
                      ),
                    ),
                  ] else ...[
                    _InkNumberField(
                      controller: _sizeCtrl,
                      label: _t(
                        isRu,
                        'Размер (см)',
                        'Size (cm)',
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _t(
                        isRu,
                        'Бюджет: ${_budget.start.round()} - ${_budget.end.round()} ₽',
                        'Budget: ${_budget.start.round()} - ${_budget.end.round()} RUB',
                      ),
                    ),
                    RangeSlider(
                      min: 0,
                      max: 300000,
                      divisions: 60,
                      values: _budget,
                      onChanged: (v) => setState(() => _budget = v),
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      initialValue: _searchMode,
                      decoration: InputDecoration(
                        labelText: _t(
                          isRu,
                          'Режим поиска',
                          'Search mode',
                        ),
                        border: const OutlineInputBorder(),
                      ),
                      items: [
                        DropdownMenuItem(
                          value: 'city',
                          child: Text(
                            _t(
                              isRu,
                              'В городе',
                              'City',
                            ),
                          ),
                        ),
                        DropdownMenuItem(
                          value: 'region',
                          child: Text(
                            _t(
                              isRu,
                              'В регионе',
                              'Region',
                            ),
                          ),
                        ),
                        DropdownMenuItem(
                          value: 'radius',
                          child: Text(
                            _t(
                              isRu,
                              'По радиусу',
                              'Radius',
                            ),
                          ),
                        ),
                      ],
                      onChanged: (v) =>
                          setState(() => _searchMode = v ?? 'city'),
                    ),
                    const SizedBox(height: 8),
                    if (_searchMode == 'city')
                      _LocationButton(
                        label: _t(isRu, 'Город поиска', 'Search city'),
                        value: _cityLocation?.label,
                        onPressed: () => _pickLocation(true),
                      ),
                    if (_searchMode == 'region') ...[
                      const SizedBox(height: 8),
                      _LocationButton(
                        label: _t(isRu, 'Область поиска', 'Search region'),
                        value: _regionLocation?.label,
                        onPressed: () => _pickLocation(false),
                      ),
                    ],
                    const SizedBox(height: 8),
                    if (_searchMode == 'radius')
                      _LocationButton(
                        label: _t(isRu, 'Радиус на карте', 'Radius on map'),
                        value: _radiusArea?.label,
                        onPressed: _pickRadiusArea,
                      ),
                    const SizedBox(height: 8),
                    Text(
                      _t(
                        isRu,
                        'Минимальный опыт: ${_expMin.round()}${_expMin.round() >= 10 ? '+' : ''} лет',
                        'Min experience: ${_expMin.round()} years',
                      ),
                    ),
                    Slider(
                      min: 0,
                      max: 10,
                      divisions: 10,
                      value: _expMin,
                      onChanged: (v) => setState(() => _expMin = v),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _t(
                        isRu,
                        'Минимальный рейтинг:',
                        'Minimum rating:',
                      ),
                    ),
                    Row(
                      children: List.generate(5, (index) {
                        final star = index + 1;
                        final active = star <= _ratingMin;
                        return IconButton(
                          onPressed: () => setState(() => _ratingMin = star),
                          icon: Icon(
                            active ? Icons.star : Icons.star_border,
                            color: Colors.amber,
                          ),
                        );
                      }),
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: _workplace,
                      decoration: InputDecoration(
                        labelText: _t(
                          isRu,
                          'Предпочитаемое место',
                          'Preferred workplace',
                        ),
                        border: const OutlineInputBorder(),
                      ),
                      items: [
                        DropdownMenuItem(
                          value: 'any',
                          child: Text(
                            _t(
                              isRu,
                              'Без разницы',
                              'Any',
                            ),
                          ),
                        ),
                        DropdownMenuItem(
                          value: 'studio',
                          child: Text(
                            _t(
                              isRu,
                              'Студия',
                              'Studio',
                            ),
                          ),
                        ),
                        DropdownMenuItem(
                          value: 'home',
                          child: Text(
                            _t(
                              isRu,
                              'У клиента дома',
                              'Home',
                            ),
                          ),
                        ),
                      ],
                      onChanged: (v) => setState(() => _workplace = v ?? 'any'),
                    ),
                    const SizedBox(height: 8),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      value: _saveDefaults,
                      onChanged: (value) =>
                          setState(() => _saveDefaults = value ?? false),
                      title: Text(
                        _t(
                          isRu,
                          'Сохранить эти параметры как предпочтения',
                          'Save these values as defaults',
                        ),
                      ),
                      subtitle: Text(
                        _t(
                          isRu,
                          'Их можно изменить позже в настройках InkMatch.',
                          'You can change them later in InkMatch settings.',
                        ),
                      ),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                  ],
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _saving ? null : _submit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: _saving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(
                              _t(
                                isRu,
                                'Создать InkMatch',
                                'Create InkMatch',
                              ),
                              style: TextStyle(
                                fontFamily: AppTypography.bodyFont(locale),
                              ),
                            ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _InkNumberField extends StatelessWidget {
  const _InkNumberField({required this.controller, required this.label});

  final TextEditingController controller;
  final String label;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _LocationButton extends StatelessWidget {
  const _LocationButton({
    required this.label,
    required this.value,
    required this.onPressed,
  });

  final String label;
  final String? value;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: const Icon(Icons.place),
      label: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          value == null || value!.isEmpty ? label : '$label: $value',
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
    );
  }
}
