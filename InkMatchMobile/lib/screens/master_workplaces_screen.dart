import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import 'location_picker_screen.dart';

class MasterWorkplacesScreen extends StatefulWidget {
  const MasterWorkplacesScreen({super.key});

  static const route = '/master-workplaces';

  @override
  State<MasterWorkplacesScreen> createState() => _MasterWorkplacesScreenState();
}

class _MasterWorkplacesScreenState extends State<MasterWorkplacesScreen> {
  final _api = ApiClient.defaultClient();
  final _studioCtrl = TextEditingController();
  final _publicTextCtrl = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  String? _error;
  List<Map<String, dynamic>> _items = const [];
  LocationPickerResult? _location;
  String _displayMode = 'street';
  bool _isPrimary = true;
  bool _showOnMap = true;
  String? _editingWorkplaceId;

  String get _token => AppSession.instance.accessToken ?? '';

  String _displayModeLabel(String value, bool isRu) {
    return switch (value) {
      'city_only' => isRu ? 'Только город' : 'City only',
      'full_address' => isRu ? 'Полный адрес' : 'Full address',
      'metro' => isRu ? 'Метро / текст' : 'Metro / text',
      _ => isRu ? 'Улица' : 'Street',
    };
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _studioCtrl.dispose();
    _publicTextCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await _api.getJson('/geo/workplaces/me', accessToken: _token);
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
          );
        });
        return;
      }
      setState(() {
        _items = (jsonDecode(res.body) as List<dynamic>)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        final current = _items.isNotEmpty
            ? (_items.firstWhere(
                (item) => (item['is_primary'] ?? false) == true,
                orElse: () => _items.first,
              ))
            : null;
        if (current != null) {
          _editingWorkplaceId = current['id']?.toString();
          _studioCtrl.text = current['studio_name']?.toString() ?? '';
          _publicTextCtrl.text =
              current['public_text_override']?.toString() ?? '';
          _displayMode =
              current['public_display_mode']?.toString() ?? 'street';
          _isPrimary = (current['is_primary'] ?? true) == true;
          _showOnMap = (current['show_on_map'] ?? true) == true;
          if (current['location'] is Map) {
            _location = LocationPickerResult(
              Map<String, dynamic>.from(current['location'] as Map),
            );
          }
        }
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

  Future<void> _pickLocation() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    final result = await Navigator.push<LocationPickerResult>(
      context,
      MaterialPageRoute(
        builder: (_) => LocationPickerScreen(
          title: isRu ? 'Ваш адрес' : 'Your address',
        ),
      ),
    );
    if (result == null || !mounted) return;
    setState(() {
      _location = result;
      _displayMode = (result.location['selected_metro_station'] as Map?) == null ? 'street' : 'metro';
    });
  }

  Future<void> _save() async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    if (_saving) return;
    if (_location == null) {
      setState(() => _error = isRu ? 'Выберите адрес' : 'Choose address');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final isEdit = _editingWorkplaceId != null;
      final res = isEdit
          ? await _api.patchJson('/geo/workplaces/me/$_editingWorkplaceId', {
              'location_id': _location!.id,
              'is_home_studio': false,
              'studio_name': _studioCtrl.text.trim().isEmpty
                  ? null
                  : _studioCtrl.text.trim(),
              'public_display_mode': _displayMode,
              'public_metro_station_id': (_location?.location['selected_metro_station'] as Map?)?['id']?.toString(),
              'public_text_override': _publicTextCtrl.text.trim().isEmpty
                  ? null
                  : _publicTextCtrl.text.trim(),
              'show_on_map': _showOnMap,
              'public_lat': _location!.lat,
              'public_lon': _location!.lon,
              'is_primary': _isPrimary,
            }, accessToken: _token)
          : await _api.postJson('/geo/workplaces/me', {
              'location_id': _location!.id,
              'is_home_studio': false,
              'studio_name': _studioCtrl.text.trim().isEmpty
                  ? null
                  : _studioCtrl.text.trim(),
        'public_display_mode': _displayMode,
        'public_metro_station_id': (_location?.location['selected_metro_station'] as Map?)?['id']?.toString(),
        'public_text_override': _publicTextCtrl.text.trim().isEmpty
            ? null
            : _publicTextCtrl.text.trim(),
        'show_on_map': _showOnMap,
        'public_lat': _location!.lat,
              'public_lon': _location!.lon,
              'is_primary': _isPrimary,
            }, accessToken: _token);
      if (!mounted) return;
      if (res.statusCode != 200 && res.statusCode != 201) {
        setState(() {
          _saving = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
          );
        });
        return;
      }
      _studioCtrl.clear();
      _publicTextCtrl.clear();
      _location = null;
      _editingWorkplaceId = null;
      await _load();
      if (mounted) setState(() => _saving = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _delete(String id) async {
    final res = await _api.deleteJson(
      '/geo/workplaces/me/$id',
      accessToken: _token,
    );
    if (res.statusCode == 204) {
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: Text(isRu ? 'Адреса мастера' : 'Master addresses')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(
                      _error!,
                      style: TextStyle(color: Colors.red.shade800),
                    ),
                  ),
                ..._items.map(
                  (item) => Card(
                    child: ListTile(
                      leading: Icon(
                        (item['is_primary'] ?? false) == true
                            ? Icons.star
                            : Icons.place,
                        color: (item['is_primary'] ?? false) == true
                            ? Colors.amber
                            : null,
                      ),
                      title: Text(item['public_address']?.toString() ?? ''),
                      subtitle: Text(
                        [
                          _displayModeLabel(
                            item['public_display_mode']?.toString() ?? 'street',
                            isRu,
                          ),
                          (item['public_metro_station'] as Map?)?['name']?.toString(),
                        ].whereType<String>().join(' · '),
                      ),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () => _delete(item['id'].toString()),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  isRu ? 'Текущий адрес' : 'Current address',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _studioCtrl,
                  decoration: InputDecoration(
                    labelText: isRu ? 'Название студии' : 'Studio name',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _pickLocation,
                  icon: const Icon(Icons.place),
                  label: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      _location?.label ??
                          (isRu ? 'Выбрать адрес' : 'Choose address'),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: _displayMode,
                  decoration: InputDecoration(
                    labelText: isRu ? 'Показывать публично' : 'Public display',
                    border: const OutlineInputBorder(),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: 'city_only',
                      child: Text(isRu ? 'Только город' : 'City only'),
                    ),
                    DropdownMenuItem(
                      value: 'street',
                      child: Text(isRu ? 'Улица' : 'Street'),
                    ),
                    DropdownMenuItem(
                      value: 'full_address',
                      child: Text(isRu ? 'Полный адрес' : 'Full address'),
                    ),
                    DropdownMenuItem(
                      value: 'metro',
                      child: Text(isRu ? 'Метро / текст' : 'Metro / text'),
                    ),
                  ],
                  onChanged: (value) =>
                      setState(() => _displayMode = value ?? 'street'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _publicTextCtrl,
                  decoration: InputDecoration(
                    labelText: isRu
                        ? 'Публичный текст вместо адреса'
                        : 'Public text override',
                    border: const OutlineInputBorder(),
                  ),
                ),
                SwitchListTile(
                  value: _isPrimary,
                  onChanged: (value) => setState(() => _isPrimary = value),
                  title: Text(isRu ? 'Основной адрес' : 'Primary address'),
                ),
                SwitchListTile(
                  value: _showOnMap,
                  onChanged: (value) => setState(() => _showOnMap = value),
                  title: Text(isRu ? 'Показывать на карте' : 'Show on map'),
                ),
                ElevatedButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.save),
                  label: Text(
                    _editingWorkplaceId == null
                        ? (isRu ? 'Сохранить адрес' : 'Save address')
                        : (isRu ? 'Изменить адрес' : 'Update address'),
                  ),
                ),
              ],
            ),
    );
  }
}
