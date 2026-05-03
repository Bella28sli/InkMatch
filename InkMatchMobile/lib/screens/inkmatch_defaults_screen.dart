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

class InkmatchDefaultsScreen extends StatefulWidget {
  const InkmatchDefaultsScreen({super.key});

  static const route = '/inkmatch-defaults';

  @override
  State<InkmatchDefaultsScreen> createState() => _InkmatchDefaultsScreenState();
}

class _InkmatchDefaultsScreenState extends State<InkmatchDefaultsScreen> {
  final _api = ApiClient.defaultClient();

  final _sizeCtrl = TextEditingController();
  final _priceMinCtrl = TextEditingController();
  final _priceMaxCtrl = TextEditingController();
  final _expMinCtrl = TextEditingController();
  final _ratingMinCtrl = TextEditingController();
  final _radiusCtrl = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  String? _error;

  String _searchMode = 'city';
  String _workplace = 'any';
  LocationPickerResult? _cityLocation;
  LocationPickerResult? _regionLocation;
  MapPointPickerResult? _radiusArea;

  String get _token => AppSession.instance.accessToken ?? '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _sizeCtrl.dispose();
    _priceMinCtrl.dispose();
    _priceMaxCtrl.dispose();
    _expMinCtrl.dispose();
    _ratingMinCtrl.dispose();
    _radiusCtrl.dispose();
    super.dispose();
  }

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

    try {
      final res = await _api.getJson(
        '/account/inkmatch-defaults',
        accessToken: _token,
      );
      if (!mounted) {
        return;
      }

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        _sizeCtrl.text = (data['default_size_sm'] ?? '').toString();
        _priceMinCtrl.text = (data['default_price_min'] ?? '').toString();
        _priceMaxCtrl.text = (data['default_price_max'] ?? '').toString();
        _expMinCtrl.text = (data['experience_years_min'] ?? '').toString();
        _ratingMinCtrl.text = (data['rating_min'] ?? '').toString();
        _radiusCtrl.text = (data['radius_meters'] ?? '').toString();
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
      } else if (res.statusCode == 404) {
        // No defaults yet: keep fields empty so user can fill them.
      }

      setState(() {
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

  int? _toInt(TextEditingController ctrl) {
    final value = ctrl.text.trim();
    if (value.isEmpty) {
      return null;
    }
    return int.tryParse(value);
  }

  double? _toDouble(TextEditingController ctrl) {
    final value = ctrl.text.trim();
    if (value.isEmpty) {
      return null;
    }
    return double.tryParse(value.replaceAll(',', '.'));
  }

  String _workplaceLabel(String value, bool isRu) {
    return switch (value) {
      'studio' => isRu ? 'Студия' : 'Studio',
      'home' => isRu ? 'На дому' : 'Home',
      _ => isRu ? 'Неважно' : 'Any',
    };
  }

  String _searchModeLabel(String value, bool isRu) {
    return switch (value) {
      'region' => isRu ? 'Область' : 'Region',
      'radius' => isRu ? 'Радиус на карте' : 'Map radius',
      _ => isRu ? 'Город' : 'City',
    };
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
              ? (isRu ? 'Город поиска' : 'Search city')
              : (isRu ? 'Регион поиска' : 'Search region'),
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
          title: isRu ? 'Радиус поиска' : 'Search radius',
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

  Future<void> _save() async {
    if (_saving || _token.isEmpty) {
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final res = await _api.putJson('/account/inkmatch-defaults', {
        'experience_years_min': _toInt(_expMinCtrl),
        'rating_min': _toDouble(_ratingMinCtrl),
        'workplace': _workplace,
        'search_mode': _searchMode,
        'city_location_id': _cityLocation?.id,
        'region_location_id': _regionLocation?.id,
        'center_lat': _radiusArea?.lat ?? _cityLocation?.lat,
        'center_lon': _radiusArea?.lon ?? _cityLocation?.lon,
        'radius_meters': _radiusArea?.radiusMeters ?? _toInt(_radiusCtrl),
        'default_size_sm': _toInt(_sizeCtrl),
        'default_price_min': _toInt(_priceMinCtrl),
        'default_price_max': _toInt(_priceMaxCtrl),
      }, accessToken: _token);

      if (!mounted) {
        return;
      }

      if (res.statusCode != 200) {
        setState(() {
          _saving = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Не удалось сохранить настройки InkMatch'
                : 'Failed to save InkMatch settings',
          );
        });
        return;
      }

      setState(() {
        _saving = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Настройки InkMatch сохранены'
                : 'InkMatch settings saved',
          ),
        ),
      );
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) {
        return;
      }
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
          isRu ? 'Базовые предпочтения InkMatch' : 'InkMatch defaults',
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
                  _InkNumberField(
                    controller: _sizeCtrl,
                    label: isRu
                        ? 'Размер по умолчанию (см)'
                        : 'Default size (cm)',
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: _InkNumberField(
                          controller: _priceMinCtrl,
                          label: isRu ? 'Бюджет от' : 'Budget from',
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _InkNumberField(
                          controller: _priceMaxCtrl,
                          label: isRu ? 'Бюджет до' : 'Budget to',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (_searchMode == 'city')
                    _LocationButton(
                      label: isRu ? 'Город поиска' : 'Search city',
                      value: _cityLocation?.label,
                      onPressed: () => _pickLocation(true),
                    ),
                  if (_searchMode == 'region') ...[
                    const SizedBox(height: 8),
                    _LocationButton(
                      label: isRu ? 'Область поиска' : 'Search region',
                      value: _regionLocation?.label,
                      onPressed: () => _pickLocation(false),
                    ),
                  ],
                  const SizedBox(height: 8),
                  _InkNumberField(
                    controller: _expMinCtrl,
                    label: isRu ? 'Мин. опыт мастера' : 'Min master experience',
                  ),
                  const SizedBox(height: 8),
                  _InkNumberField(
                    controller: _ratingMinCtrl,
                    label: isRu ? 'Мин. рейтинг мастера' : 'Min master rating',
                    allowDecimal: true,
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: _workplace,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Предпочтительное место'
                          : 'Preferred workplace',
                      border: const OutlineInputBorder(),
                    ),
                    items: ['any', 'studio', 'home']
                        .map(
                          (value) => DropdownMenuItem(
                            value: value,
                            child: Text(_workplaceLabel(value, isRu)),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value == null) {
                        return;
                      }
                      setState(() {
                        _workplace = value;
                      });
                    },
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: _searchMode,
                    decoration: InputDecoration(
                      labelText: isRu ? 'Режим поиска' : 'Search mode',
                      border: const OutlineInputBorder(),
                    ),
                    items: ['city', 'region', 'radius']
                        .map(
                          (value) => DropdownMenuItem(
                            value: value,
                            child: Text(_searchModeLabel(value, isRu)),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value == null) {
                        return;
                      }
                      setState(() {
                        _searchMode = value;
                      });
                    },
                  ),
                  const SizedBox(height: 8),
                  if (_searchMode == 'radius')
                    _LocationButton(
                      label: isRu ? 'Радиус на карте' : 'Radius on map',
                      value: _radiusArea?.label,
                      onPressed: _pickRadiusArea,
                    ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _saving ? null : _save,
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
                              isRu ? 'Сохранить' : 'Save',
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
  const _InkNumberField({
    required this.controller,
    required this.label,
    this.allowDecimal = false,
  });

  final TextEditingController controller;
  final String label;
  final bool allowDecimal;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: allowDecimal
          ? const TextInputType.numberWithOptions(decimal: true)
          : TextInputType.number,
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
