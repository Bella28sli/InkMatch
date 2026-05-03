import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'map_point_picker_screen.dart';
import 'metro_station_picker_screen.dart';

class LocationPickerResult {
  const LocationPickerResult(this.location);

  final Map<String, dynamic> location;

  String get id => location['id']?.toString() ?? '';
  double? get lat => (location['lat'] as num?)?.toDouble();
  double? get lon => (location['lon'] as num?)?.toDouble();
  String get label =>
      location['display_label']?.toString() ??
      location['short_label']?.toString() ??
      location['locality']?.toString() ??
      '';
}

class LocationPickerScreen extends StatefulWidget {
  const LocationPickerScreen({super.key, this.title, this.precisionLevel});

  final String? title;
  final String? precisionLevel;

  @override
  State<LocationPickerScreen> createState() => _LocationPickerScreenState();
}

class _LocationPickerScreenState extends State<LocationPickerScreen> {
  final _api = ApiClient.defaultClient();
  final _searchCtrl = TextEditingController();
  final _countryCtrl = TextEditingController(text: 'Россия');
  final _regionCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _streetCtrl = TextEditingController();
  final _entranceCtrl = TextEditingController();
  final _countryFocus = FocusNode();
  final _regionFocus = FocusNode();
  final _cityFocus = FocusNode();
  final _streetFocus = FocusNode();

  Timer? _debounce;
  bool _loading = false;
  bool _creating = false;
  String? _error;
  List<Map<String, dynamic>> _items = const [];
  String? _selectedLocationId;
  Map<String, dynamic>? _selectedMetroStation;
  bool? _hasMetroForSelectedLocation;
  double? _pickedLat;
  double? _pickedLon;
  List<Map<String, dynamic>> _countrySuggestions = const [];
  List<Map<String, dynamic>> _regionSuggestions = const [];
  List<Map<String, dynamic>> _citySuggestions = const [];
  List<Map<String, dynamic>> _streetSuggestions = const [];
  List<Map<String, dynamic>> _nearbyMetroStations = const [];

  String get _token => AppSession.instance.accessToken ?? '';

  @override
  void dispose() {
    _debounce?.cancel();
    _searchCtrl.dispose();
    _countryCtrl.dispose();
    _regionCtrl.dispose();
    _cityCtrl.dispose();
    _streetCtrl.dispose();
    _entranceCtrl.dispose();
    _countryFocus.dispose();
    _regionFocus.dispose();
    _cityFocus.dispose();
    _streetFocus.dispose();
    super.dispose();
  }

  void _onSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), _load);
  }

  void _onCityChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 300),
      () => _loadSuggestions(value, target: 'city'),
    );
  }

  void _onCountryChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 300),
      () => _loadSuggestions(value, target: 'country'),
    );
  }

  void _onRegionChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 300),
      () => _loadSuggestions(value, target: 'region'),
    );
  }

  void _onStreetChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: 300),
      () => _loadSuggestions(value, target: 'street'),
    );
  }

  void _applySuggestion(Map<String, dynamic> item) {
    final country = item['country']?.toString().trim();
    final region = item['region']?.toString().trim();
    final city = item['locality']?.toString().trim();
    final street = item['address_line']?.toString().trim();
    final previousCity = _cityCtrl.text.trim();

    if (country != null && country.isNotEmpty) {
      _countryCtrl.text = country;
    }
    if (region != null && region.isNotEmpty) {
      _regionCtrl.text = region;
    }
    if (city != null && city.isNotEmpty) {
      _cityCtrl.text = city;
    }
    if (street != null && street.isNotEmpty) {
      _streetCtrl.text = street;
    }

    final lat = item['lat'];
    final lon = item['lon'];
    if (lat is num) _pickedLat = lat.toDouble();
    if (lon is num) _pickedLon = lon.toDouble();

    final locationId = item['id']?.toString() ?? '';
    if (locationId.isNotEmpty) {
      _selectedLocationId = locationId;
      if (city != null && city.isNotEmpty && city != previousCity) {
        _selectedMetroStation = null;
        _hasMetroForSelectedLocation = null;
        _checkMetroAvailability(locationId);
      }
    }

    setState(() {
      _countrySuggestions = const [];
      _regionSuggestions = const [];
      _citySuggestions = const [];
      _streetSuggestions = const [];
      _error = null;
    });
    FocusScope.of(context).unfocus();
  }

  void _applyLocationItem(Map<String, dynamic> item) {
    final country = item['country']?.toString().trim();
    final region = item['region']?.toString().trim();
    final city = item['locality']?.toString().trim();
    final street = item['address_line']?.toString().trim();
    final lat = item['lat'];
    final lon = item['lon'];

    if (country != null && country.isNotEmpty) _countryCtrl.text = country;
    if (region != null && region.isNotEmpty) _regionCtrl.text = region;
    if (city != null && city.isNotEmpty) _cityCtrl.text = city;
    if (street != null && street.isNotEmpty) _streetCtrl.text = street;
    if (lat is num) _pickedLat = lat.toDouble();
    if (lon is num) _pickedLon = lon.toDouble();
    _selectedLocationId = item['id']?.toString();
    _countrySuggestions = const [];
    _regionSuggestions = const [];
    _citySuggestions = const [];
    _streetSuggestions = const [];
    _nearbyMetroStations = const [];
    _items = const [];
    _searchCtrl.clear();
    _error = null;
    setState(() {});
    if (_selectedLocationId != null && _selectedLocationId!.isNotEmpty) {
      _checkMetroAvailability(_selectedLocationId!);
      _loadNearbyMetroStations(_selectedLocationId!);
    }
  }

  List<Map<String, dynamic>> _dedupe(List<Map<String, dynamic>> items) {
    final seen = <String>{};
    final result = <Map<String, dynamic>>[];
    for (final item in items) {
      final key = [
        item['display_label']?.toString().trim().toLowerCase() ?? '',
        item['address_line']?.toString().trim().toLowerCase() ?? '',
      ].join('|');
      if (seen.add(key)) result.add(item);
    }
    return result;
  }

  Future<void> _load() async {
    final query = _searchCtrl.text.trim();
    if (query.length < 3) {
      setState(() => _items = const []);
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await _api.getJson(
        '/geo/geocode',
        query: {
          'q': query,
          'limit': '8',
          if (widget.precisionLevel != null) 'precision_level': widget.precisionLevel!,
        },
      );
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(context, res.statusCode, res.body);
        });
        return;
      }
      final items = _dedupe(
        (jsonDecode(res.body) as List<dynamic>)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
      );
      setState(() {
        _items = items;
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

  Future<void> _loadSuggestions(String query, {required String target}) async {
    final value = query.trim();
    if (value.length < 3) {
      if (!mounted) return;
      setState(() {
        if (target == 'city') {
          _citySuggestions = const [];
        } else if (target == 'country') {
          _countrySuggestions = const [];
        } else if (target == 'region') {
          _regionSuggestions = const [];
        } else {
          _streetSuggestions = const [];
        }
      });
      return;
    }

    try {
      final res = await _api.getJson(
        '/geo/geocode',
        query: {'q': value, 'limit': '5'},
      );
      if (!mounted || res.statusCode != 200) return;
      final items = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      setState(() {
        if (target == 'city') {
          _citySuggestions = items;
        } else if (target == 'country') {
          _countrySuggestions = items;
        } else if (target == 'region') {
          _regionSuggestions = items;
        } else {
          _streetSuggestions = items;
        }
      });
    } catch (_) {}
  }

  Future<void> _pickOnMap() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<MapPointPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => MapPointPickerScreen(
          title: isRu ? 'Выберете адрес на карте' : 'Pick address on map',
        ),
      ),
    );
    if (result == null || !mounted) return;

    Map<String, dynamic>? candidate;
    try {
      final geoRes = await _api.getJson(
        '/geo/geocode',
        query: {'q': '${result.lon},${result.lat}', 'limit': '3'},
      ).timeout(const Duration(seconds: 8));
      if (geoRes.statusCode == 200) {
        final list = jsonDecode(geoRes.body) as List<dynamic>;
        if (list.isNotEmpty) {
          candidate = Map<String, dynamic>.from(list.first as Map);
        }
      }
    } catch (_) {}

    _countryCtrl.text =
        candidate?['country']?.toString().trim().isNotEmpty == true
            ? candidate!['country'].toString()
            : '';
    _regionCtrl.text =
        candidate?['region']?.toString().trim().isNotEmpty == true
            ? candidate!['region'].toString()
            : '';
    _cityCtrl.text =
        candidate?['locality']?.toString().trim().isNotEmpty == true
            ? candidate!['locality'].toString()
            : '';
    _streetCtrl.text =
        candidate?['address_line']?.toString().trim().isNotEmpty == true
            ? candidate!['address_line'].toString()
            : '';
    _citySuggestions = const [];
    _streetSuggestions = const [];
    _selectedLocationId = candidate?['id']?.toString();
    _selectedMetroStation = null;
    _hasMetroForSelectedLocation = null;
    _pickedLat = result.lat;
    _pickedLon = result.lon;
    setState(() {
      _error = null;
    });
  }

  Future<void> _checkMetroAvailability(String locationId) async {
    final res = await _api.getJson(
      '/geo/metro-stations',
      accessToken: _token,
      query: {'near_location_id': locationId},
    );
    if (!mounted || res.statusCode != 200) return;
    final items = jsonDecode(res.body) as List<dynamic>;
    setState(() => _hasMetroForSelectedLocation = items.isNotEmpty);
  }

  Future<void> _loadNearbyMetroStations(String locationId) async {
    try {
      final res = await _api.getJson(
        '/geo/metro-stations/nearest',
        query: {'location_id': locationId, 'limit': '5'},
      );
      if (!mounted || res.statusCode != 200) return;
      final items = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      setState(() => _nearbyMetroStations = items);
    } catch (_) {}
  }

  Future<void> _pickMetroStation() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<MetroStationPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => MetroStationPickerScreen(
          nearLocationId: _selectedLocationId,
          title: isRu ? 'Выберете станцию метро' : 'Pick metro station',
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      _selectedMetroStation = result.station;
    });
  }

  Future<void> _createManual() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final city = _cityCtrl.text.trim();
    final street = _streetCtrl.text.trim();
    if (city.isEmpty) {
      setState(() => _error = isRu ? 'Выберете город' : 'Enter city');
      return;
    }

    setState(() {
      _creating = true;
      _error = null;
    });

    try {
      final res = await _api.postJson(
        '/geo/locations/ensure',
        {
          'country': _countryCtrl.text.trim().isEmpty ? 'Россия' : _countryCtrl.text.trim(),
          'region': _regionCtrl.text.trim().isEmpty ? null : _regionCtrl.text.trim(),
          'locality': city,
          'address_line': street.isEmpty ? null : street,
          'entrance': _entranceCtrl.text.trim().isEmpty ? null : _entranceCtrl.text.trim(),
          'lat': _pickedLat,
          'lon': _pickedLon,
          'precision_level': street.isEmpty ? 'locality' : 'exact',
        },
        accessToken: _token,
      );

      if (!mounted) return;
      if (res.statusCode != 200 && res.statusCode != 201) {
        setState(() {
          _creating = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: isRu ? 'Не удалось сохранить адрес' : 'Failed to save address',
          );
        });
        return;
      }
      final location = Map<String, dynamic>.from(jsonDecode(res.body) as Map);
      location['entrance'] = _entranceCtrl.text.trim().isEmpty ? null : _entranceCtrl.text.trim();
      location['country'] = _countryCtrl.text.trim();
      location['region'] = _regionCtrl.text.trim();
      location['address_line'] = street.isEmpty ? null : street;
      if (_selectedMetroStation != null) {
        location['selected_metro_station'] = _selectedMetroStation;
      }
      _selectedLocationId = location['id']?.toString();
      _applyLocationItem(location);
      await _checkMetroAvailability(_selectedLocationId!);
      await _loadNearbyMetroStations(_selectedLocationId!);
      if (!mounted) return;
      Navigator.pop(context, LocationPickerResult(location));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _creating = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  Future<void> _selectLocation(Map<String, dynamic> item) async {
    _applyLocationItem(item);
    final locationId = item['id']?.toString() ?? '';
    if (locationId.isNotEmpty) {
      return;
    }

    final res = await _api.postJson(
      '/geo/locations/ensure',
      {
        'country': _countryCtrl.text.trim().isEmpty ? 'Россия' : _countryCtrl.text.trim(),
        'region': _regionCtrl.text.trim().isEmpty ? null : _regionCtrl.text.trim(),
        'locality': _cityCtrl.text.trim().isEmpty ? (item['locality']?.toString() ?? item['display_label']?.toString() ?? 'Адрес') : _cityCtrl.text.trim(),
        'address_line': _streetCtrl.text.trim().isEmpty ? item['address_line'] : _streetCtrl.text.trim(),
        'postal_code': item['postal_code'],
        'entrance': _entranceCtrl.text.trim().isEmpty ? null : _entranceCtrl.text.trim(),
        'lat': item['lat'] ?? _pickedLat,
        'lon': item['lon'] ?? _pickedLon,
        'precision_level': item['precision_level'] ?? 'exact',
      },
    );
    if (!mounted) return;
    if (res.statusCode == 200 || res.statusCode == 201) {
      final location = Map<String, dynamic>.from(jsonDecode(res.body) as Map);
      if (_selectedMetroStation != null) {
        location['selected_metro_station'] = _selectedMetroStation;
      }
      _selectedLocationId = location['id']?.toString();
      _applyLocationItem(location);
      await _checkMetroAvailability(_selectedLocationId!);
      await _loadNearbyMetroStations(_selectedLocationId!);
      if (!mounted) return;
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(widget.title ?? (isRu ? 'Адрес' : 'Address')),
        backgroundColor: AppColors.background,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _searchCtrl,
            onChanged: _onSearch,
            decoration: InputDecoration(
              labelText: isRu ? 'Поиск адреса' : 'Search address',
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _pickOnMap,
            icon: const Icon(Icons.map_outlined),
            label: Text(isRu ? 'Выбрать на карте' : 'Pick on map'),
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(_error!, style: TextStyle(color: Colors.red.shade800)),
            ),
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_items.isEmpty && _searchCtrl.text.trim().length >= 3)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(isRu ? 'Ничего не найдено' : 'Nothing found'),
            )
          else if (_items.isNotEmpty)
            ..._items.map(
              (item) => Card(
                child: ListTile(
                  leading: const Icon(Icons.place),
                  title: Text(item['display_label']?.toString() ?? ''),
                  onTap: () => _selectLocation(item),
                ),
              ),
            ),
          const SizedBox(height: 18),
          Text(
            isRu ? 'Добавить вручную' : 'Add manually',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 20,
            ),
          ),
          const SizedBox(height: 8),
          _fieldWithSuggestions(
            controller: _countryCtrl,
            focusNode: _countryFocus,
            label: isRu ? 'Страна' : 'Country',
            onChanged: _onCountryChanged,
            suggestions: _countrySuggestions,
            onPick: _applySuggestion,
          ),
          _fieldWithSuggestions(
            controller: _regionCtrl,
            focusNode: _regionFocus,
            label: isRu ? 'Регион' : 'Region',
            onChanged: _onRegionChanged,
            suggestions: _regionSuggestions,
            onPick: _applySuggestion,
          ),
          _fieldWithSuggestions(
            controller: _cityCtrl,
            focusNode: _cityFocus,
            label: isRu ? 'Город' : 'City',
            onChanged: _onCityChanged,
            suggestions: _citySuggestions,
            onPick: _applySuggestion,
          ),
          _fieldWithSuggestions(
            controller: _streetCtrl,
            focusNode: _streetFocus,
            label: isRu ? 'Улица, дом' : 'Street, building',
            onChanged: _onStreetChanged,
            suggestions: _streetSuggestions,
            onPick: _applySuggestion,
          ),
          _field(_entranceCtrl, isRu ? 'Подъезд' : 'Entrance'),
          const SizedBox(height: 4),
          if (_selectedLocationId != null && _selectedLocationId!.isNotEmpty) ...[
            if (_nearbyMetroStations.isNotEmpty) ...[
              Text(
                isRu ? 'Ближайшие станции метро' : 'Nearby metro stations',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: AppColors.ink.withValues(alpha: 0.8),
                ),
              ),
              const SizedBox(height: 6),
              ..._nearbyMetroStations.map(
                (station) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: () => setState(() {
                      _selectedMetroStation = station;
                      _hasMetroForSelectedLocation = true;
                    }),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      decoration: BoxDecoration(
                        color: _selectedMetroStation == station
                            ? AppColors.accent.withValues(alpha: 0.10)
                            : Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: _selectedMetroStation == station
                              ? AppColors.accent.withValues(alpha: 0.45)
                              : AppColors.ink.withValues(alpha: 0.10),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.directions_subway_outlined, size: 18),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  station['name']?.toString() ?? '',
                                  style: const TextStyle(fontWeight: FontWeight.w600),
                                ),
                                if ((station['line_name']?.toString().trim().isNotEmpty ?? false))
                                  Text(
                                    station['line_name']?.toString() ?? '',
                                    style: TextStyle(color: AppColors.ink.withValues(alpha: 0.7)),
                                  ),
                              ],
                            ),
                          ),
                          Text(
                            '${(station['distance_m'] as num?)?.round() ?? 0} м',
                            style: TextStyle(color: AppColors.ink.withValues(alpha: 0.7)),
                          ),
                          if (_selectedMetroStation == station) ...[
                            const SizedBox(width: 8),
                            Icon(Icons.check_circle, size: 18, color: AppColors.accent),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 6),
            ],
            if (_hasMetroForSelectedLocation == true)
              OutlinedButton.icon(
                onPressed: _pickMetroStation,
                icon: const Icon(Icons.directions_subway_outlined),
                label: Text(
                  _selectedMetroStation?['name']?.toString() ??
                      (isRu ? 'Выбрать метро' : 'Choose metro'),
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  isRu
                      ? 'Для этого адреса метро не найдено'
                      : 'No metro is available for this address',
                  style: TextStyle(color: AppColors.ink.withValues(alpha: 0.7)),
                ),
              ),
          ],
          const SizedBox(height: 8),
          ElevatedButton.icon(
            onPressed: _creating ? null : _createManual,
            icon: const Icon(Icons.add_location_alt),
            label: Text(isRu ? 'Сохранить адрес' : 'Save address'),
          ),
        ],
      ),
    );
  }

  Widget _field(TextEditingController controller, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextField(
        controller: controller,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Widget _fieldWithSuggestions({
    required TextEditingController controller,
    required FocusNode focusNode,
    required String label,
    required ValueChanged<String> onChanged,
    required List<Map<String, dynamic>> suggestions,
    required void Function(Map<String, dynamic>) onPick,
  }) {
    final query = controller.text.trim().toLowerCase();
    final visible = query.length >= 3 ? suggestions.take(6).toList() : const <Map<String, dynamic>>[];
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: controller,
            focusNode: focusNode,
            onChanged: onChanged,
            decoration: InputDecoration(
              labelText: label,
              border: const OutlineInputBorder(),
            ),
          ),
          if (visible.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(top: 6),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.ink.withValues(alpha: 0.12)),
              ),
              constraints: const BoxConstraints(maxHeight: 260),
              child: ListView.separated(
                padding: EdgeInsets.zero,
                shrinkWrap: true,
                itemCount: visible.length,
                separatorBuilder: (context, index) =>
                    Divider(height: 1, color: AppColors.ink.withValues(alpha: 0.08)),
                itemBuilder: (context, index) {
                  final item = visible[index];
                  final address = (item['address_line']?.toString().trim().isNotEmpty == true
                          ? item['address_line'].toString().trim()
                          : item['display_label']?.toString().trim() ?? '')
                      .trim();
                  final locationBits = <String>[
                    item['country']?.toString().trim() ?? '',
                    item['locality']?.toString().trim() ?? '',
                  ].where((value) => value.isNotEmpty).toList();
                  return ListTile(
                    dense: true,
                    leading: const Icon(Icons.place_outlined, size: 18),
                    title: Text(
                      address,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: locationBits.isEmpty
                        ? null
                        : Text(locationBits.join(', ')),
                    onTap: () {
                      onPick(item);
                      setState(() => _items = const []);
                    },
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}

