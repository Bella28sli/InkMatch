import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';

class MetroStationPickerResult {
  const MetroStationPickerResult(this.station);

  final Map<String, dynamic> station;

  String get id => station['id']?.toString() ?? '';
  String get name => station['name']?.toString() ?? '';
  String get lineName => station['line_name']?.toString() ?? '';
  String get colorHex => station['color_hex']?.toString() ?? '#777777';
  String get label => [name, lineName].where((v) => v.isNotEmpty).join(', ');
}

class MetroStationPickerScreen extends StatefulWidget {
  const MetroStationPickerScreen({
    super.key,
    this.nearLocationId,
    this.title,
  });

  final String? nearLocationId;
  final String? title;

  @override
  State<MetroStationPickerScreen> createState() => _MetroStationPickerScreenState();
}

class _MetroStationPickerScreenState extends State<MetroStationPickerScreen> {
  final _api = ApiClient.defaultClient();
  final _searchCtrl = TextEditingController();

  Timer? _debounce;
  bool _loading = true;
  String? _error;
  String? _selectedLine;
  List<Map<String, dynamic>> _items = const [];

  String get _token => AppSession.instance.accessToken ?? '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final query = <String, String>{
        if (widget.nearLocationId != null) 'near_location_id': widget.nearLocationId!,
        if (_searchCtrl.text.trim().isNotEmpty) 'q': _searchCtrl.text.trim(),
        if (_selectedLine != null && _selectedLine!.isNotEmpty) 'line_name': _selectedLine!,
      };
      final res = await _api.getJson('/geo/metro-stations', accessToken: _token, query: query);
      if (!mounted) return;
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(context, res.statusCode, res.body);
        });
        return;
      }
      final items = (jsonDecode(res.body) as List<dynamic>)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
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

  void _onSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), _load);
  }

  Color _lineColor(String? raw) {
    final value = (raw == null || raw.isEmpty ? '#777777' : raw).replaceFirst('#', '');
    final parsed = int.tryParse(value, radix: 16);
    if (parsed == null) return Colors.grey;
    return Color(0xFF000000 | parsed);
  }

  List<String> get _lines {
    final values = _items
        .map((item) => item['line_name']?.toString() ?? '')
        .where((line) => line.isNotEmpty)
        .toSet()
        .toList();
    values.sort();
    return values;
  }

  @override
  Widget build(BuildContext context) {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        title: Text(widget.title ?? (isRu ? 'Станция метро' : 'Metro station')),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _searchCtrl,
            onChanged: _onSearch,
            decoration: InputDecoration(
              labelText: isRu ? 'Поиск станции или линии' : 'Search station or line',
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          if (_lines.isNotEmpty)
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(isRu ? 'Все линии' : 'All lines'),
                      selected: _selectedLine == null,
                      onSelected: (_) {
                        setState(() => _selectedLine = null);
                        _load();
                      },
                    ),
                  ),
                  ..._lines.map((line) {
                    final color = _lineColor(
                      _items.firstWhere(
                        (item) => item['line_name']?.toString() == line,
                        orElse: () => const {},
                      )['color_hex']?.toString(),
                    );
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        avatar: CircleAvatar(backgroundColor: color, radius: 6),
                        label: Text(line),
                        selected: _selectedLine == line,
                        onSelected: (_) {
                          setState(() => _selectedLine = line);
                          _load();
                        },
                      ),
                    );
                  }),
                ],
              ),
            ),
          const SizedBox(height: 12),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(_error!, style: TextStyle(color: Colors.red.shade800)),
            ),
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_items.isEmpty)
            Text(
              isRu
                  ? 'Станции метро для этого города пока не добавлены в справочник.'
                  : 'No metro stations are available for this city yet.',
            )
          else
            ..._items.map((item) {
              final color = _lineColor(item['color_hex']?.toString());
              return Card(
                child: ListTile(
                  leading: CircleAvatar(backgroundColor: color, radius: 9),
                  title: Text(item['name']?.toString() ?? ''),
                  subtitle: Text(item['line_name']?.toString() ?? ''),
                  onTap: () => Navigator.pop(
                    context,
                    MetroStationPickerResult(item),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}
