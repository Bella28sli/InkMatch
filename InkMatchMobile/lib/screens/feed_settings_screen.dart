import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class FeedPreferencesScreen extends StatefulWidget {
  const FeedPreferencesScreen({super.key});

  static const route = '/feed-preferences';

  @override
  State<FeedPreferencesScreen> createState() => _FeedPreferencesScreenState();
}

class _FeedPreferencesScreenState extends State<FeedPreferencesScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  bool _saving = false;
  String? _error;

  List<Map<String, dynamic>> _styles = const [];
  List<Map<String, dynamic>> _tags = const [];
  final Set<String> _selectedStyleIds = <String>{};
  final Set<String> _selectedTagIds = <String>{};

  String get _token => AppSession.instance.accessToken ?? '';

  @override
  void initState() {
    super.initState();
    _load();
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
      final stylesRes = await _api.getJson(
        '/catalogs/styles',
        accessToken: _token,
      );
      final tagsRes = await _api.getJson('/catalogs/tags', accessToken: _token);
      final prefsRes = await _api.getJson(
        '/account/feed-preferences',
        accessToken: _token,
      );

      if (!mounted) return;

      if (stylesRes.statusCode == 200) {
        _styles = (jsonDecode(stylesRes.body) as List<dynamic>)
            .cast<Map<String, dynamic>>();
      }
      if (tagsRes.statusCode == 200) {
        _tags = (jsonDecode(tagsRes.body) as List<dynamic>)
            .cast<Map<String, dynamic>>();
      }

      if (prefsRes.statusCode == 200) {
        final prefs = jsonDecode(prefsRes.body) as Map<String, dynamic>;
        final styles = (prefs['style_ids'] as List<dynamic>? ?? const []).map(
          (e) => e.toString(),
        );
        final tags = (prefs['tag_ids'] as List<dynamic>? ?? const []).map(
          (e) => e.toString(),
        );
        _selectedStyleIds
          ..clear()
          ..addAll(styles);
        _selectedTagIds
          ..clear()
          ..addAll(tags);
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

  Future<void> _save() async {
    if (_saving || _token.isEmpty) return;
    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final res = await _api.putJson('/account/feed-preferences', {
        'style_ids': _selectedStyleIds.toList(),
        'tag_ids': _selectedTagIds.toList(),
      }, accessToken: _token);

      if (!mounted) return;

      if (res.statusCode != 200) {
        setState(() {
          _saving = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Не удалось сохранить предпочтения'
                : 'Failed to save preferences',
          );
        });
        return;
      }

      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocaleScope.of(context).locale.languageCode == 'ru'
                ? 'Предпочтения сохранены'
                : 'Preferences saved',
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
          isRu ? 'Тату-предпочтения' : 'Tattoo preferences',
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
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
                      child: Text(_error!),
                    ),
                  Text(
                    isRu ? 'Стили' : 'Styles',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 22,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: _styles.map((style) {
                      final id = style['id'].toString();
                      final selected = _selectedStyleIds.contains(id);
                      return FilterChip(
                        label: Text(style['name']?.toString() ?? ''),
                        selected: selected,
                        selectedColor: AppColors.accent,
                        labelStyle: TextStyle(
                          color: selected ? Colors.white : AppColors.ink,
                        ),
                        onSelected: (v) => setState(() {
                          if (v) {
                            _selectedStyleIds.add(id);
                          } else {
                            _selectedStyleIds.remove(id);
                          }
                        }),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    isRu ? 'Теги' : 'Tags',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 22,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: _tags.map((tag) {
                      final id = tag['id'].toString();
                      final selected = _selectedTagIds.contains(id);
                      return FilterChip(
                        label: Text(tag['name']?.toString() ?? ''),
                        selected: selected,
                        selectedColor: AppColors.ink,
                        labelStyle: const TextStyle(color: Colors.white),
                        backgroundColor: AppColors.ink.withValues(alpha: 0.7),
                        onSelected: (v) => setState(() {
                          if (v) {
                            _selectedTagIds.add(id);
                          } else {
                            _selectedTagIds.remove(id);
                          }
                        }),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 18),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _saving ? null : _save,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                      ),
                      child: _saving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(isRu ? 'Сохранить' : 'Save'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
