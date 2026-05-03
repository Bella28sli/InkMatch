import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:yandex_mapkit/yandex_mapkit.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../theme/app_colors.dart';

class MapPointPickerResult {
  const MapPointPickerResult({
    required this.lat,
    required this.lon,
    this.radiusMeters,
    this.addressLabel,
  });

  final double lat;
  final double lon;
  final int? radiusMeters;
  final String? addressLabel;

  String get label {
    if (addressLabel != null && addressLabel!.trim().isNotEmpty) {
      return addressLabel!;
    }
    final base = '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}';
    if (radiusMeters == null) return base;
    return '$base, ${radiusMeters! ~/ 1000} км';
  }
}

class MapPointPickerScreen extends StatefulWidget {
  const MapPointPickerScreen({
    super.key,
    this.initialLat,
    this.initialLon,
    this.initialRadiusMeters,
    this.radiusEnabled = false,
    this.title,
  });

  final double? initialLat;
  final double? initialLon;
  final int? initialRadiusMeters;
  final bool radiusEnabled;
  final String? title;

  @override
  State<MapPointPickerScreen> createState() => _MapPointPickerScreenState();
}

class _MapPointPickerScreenState extends State<MapPointPickerScreen> {
  static const _fallbackPoint = Point(latitude: 55.7558, longitude: 37.6173);

  final _api = ApiClient.defaultClient();
  YandexMapController? _mapController;

  late Point _point = Point(
    latitude: widget.initialLat ?? _fallbackPoint.latitude,
    longitude: widget.initialLon ?? _fallbackPoint.longitude,
  );
  late double _radius = (widget.initialRadiusMeters ?? 5000).toDouble();

  bool _hasSelection = false;
  String? _selectedAddressLabel;

  @override
  void initState() {
    super.initState();
    _hasSelection = widget.initialLat != null && widget.initialLon != null;
    _requestLocationPermission();
    if (_hasSelection) {
      _selectedAddressLabel =
          '${_point.latitude.toStringAsFixed(5)}, ${_point.longitude.toStringAsFixed(5)}';
      _resolveAddress(_point);
    }
  }

  Future<void> _requestLocationPermission() async {
    await Permission.location.request();
  }

  Future<void> _resolveAddress(Point point) async {
    try {
      final res = await _api.getJson(
        '/geo/geocode',
        query: {'q': '${point.longitude},${point.latitude}', 'limit': '3'},
      );
      if (!mounted || res.statusCode != 200) return;
      final items = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (items.isEmpty) return;
      final candidate = items.first;
      final label =
          candidate['display_label']?.toString() ??
          candidate['short_label']?.toString() ??
          candidate['locality']?.toString();
      if (label != null && label.trim().isNotEmpty && mounted) {
        setState(() => _selectedAddressLabel = label.trim());
      }
    } catch (_) {}
  }

  Future<void> _selectPoint(Point point) async {
    setState(() {
      _point = point;
      _hasSelection = true;
      _selectedAddressLabel =
          '${point.latitude.toStringAsFixed(5)}, ${point.longitude.toStringAsFixed(5)}';
    });
    await _mapController?.moveCamera(
      CameraUpdate.newCameraPosition(
        CameraPosition(target: point, zoom: widget.radiusEnabled ? 10 : 15),
      ),
    );
    await _resolveAddress(point);
  }

  List<MapObject> get _mapObjects {
    final objects = <MapObject>[];
    if (widget.radiusEnabled) {
      objects.add(
        CircleMapObject(
          mapId: const MapObjectId('selected_radius'),
          circle: Circle(center: _point, radius: _radius),
          strokeColor: AppColors.accent,
          strokeWidth: 2,
          fillColor: AppColors.accent.withValues(alpha: 0.18),
        ),
      );
    }
    return objects;
  }

  void _confirm() {
    Navigator.pop(
      context,
      MapPointPickerResult(
        lat: _point.latitude,
        lon: _point.longitude,
        radiusMeters: widget.radiusEnabled ? _radius.round() : null,
        addressLabel: _selectedAddressLabel,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title ?? (isRu ? 'Выбор на карте' : 'Pick on map')),
        backgroundColor: AppColors.background,
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                YandexMap(
                  mapObjects: _mapObjects,
                  nightModeEnabled: false,
                  mapType: MapType.vector,
                  mode2DEnabled: true,
                  onMapCreated: (controller) {
                    _mapController = controller;
                    controller.moveCamera(
                      CameraUpdate.newCameraPosition(
                        CameraPosition(
                          target: _point,
                          zoom: widget.radiusEnabled ? 10 : 15,
                        ),
                      ),
                    );
                  },
                  onMapTap: _selectPoint,
                  onMapLongTap: _selectPoint,
                ),
                if (_hasSelection)
                  const IgnorePointer(
                    child: Center(
                      child: Icon(
                        Icons.place,
                        size: 48,
                        color: Colors.redAccent,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  isRu
                      ? 'Нажмите на место на карте, чтобы выбрать адрес'
                      : 'Tap a place on the map to choose an address',
                ),
                const SizedBox(height: 8),
                Text(
                  _selectedAddressLabel == null
                      ? (isRu ? 'Адрес пока не выбран' : 'No address selected yet')
                      : (isRu
                          ? 'Выбран адрес: $_selectedAddressLabel'
                          : 'Selected address: $_selectedAddressLabel'),
                  style: TextStyle(
                    color: AppColors.ink.withValues(alpha: 0.8),
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (widget.radiusEnabled) ...[
                  const SizedBox(height: 8),
                  Text(
                    isRu
                        ? 'Радиус: ${(_radius / 1000).round()} км'
                        : 'Radius: ${(_radius / 1000).round()} km',
                  ),
                  Slider(
                    min: 1000,
                    max: 100000,
                    divisions: 99,
                    value: _radius.clamp(1000, 100000),
                    onChanged: (value) => setState(() => _radius = value),
                  ),
                ],
                const SizedBox(height: 8),
                ElevatedButton.icon(
                  onPressed: _confirm,
                  icon: const Icon(Icons.check),
                  label: Text(isRu ? 'Выбрать' : 'Select'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
