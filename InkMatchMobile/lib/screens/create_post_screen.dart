import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class CreatePostScreen extends StatefulWidget {
  const CreatePostScreen({super.key});

  static const route = '/create-post';

  @override
  State<CreatePostScreen> createState() => _CreatePostScreenState();
}

class _CreatePostScreenState extends State<CreatePostScreen> {
  final _api = ApiClient.defaultClient();
  final _titleCtrl = TextEditingController();
  final _descriptionCtrl = TextEditingController();

  bool _loading = false;
  String? _error;
  String _role = AppSession.instance.role == SessionUserRole.master
      ? 'master'
      : 'client';

  String _contentType = 'sketch';
  bool _isPublic = true;

  List<XFile> _pickedFiles = const [];
  List<Map<String, dynamic>> _styles = const [];
  List<Map<String, dynamic>> _tags = const [];
  List<Map<String, dynamic>> _collections = const [];
  final Set<String> _selectedStyleIds = <String>{};
  final Set<String> _selectedTagIds = <String>{};
  String? _selectedCollectionId;

  List<String> get _allowedContentTypes {
    if (_role == 'master') {
      return const [
        'sketch',
        'final_work',
        'portfolio',
        'process',
        'materials',
        'find_us',
        'achievments',
      ];
    }
    return const ['sketch', 'final_work'];
  }

  @override
  void initState() {
    super.initState();
    _boot();
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descriptionCtrl.dispose();
    super.dispose();
  }

  Future<void> _boot() async {
    await _loadRefs();
    await _loadMyRole();
  }

  Future<void> _loadMyRole() async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;

    try {
      final meRes = await _api.getJson('/profiles/me/full', accessToken: token);
      if (meRes.statusCode != 200 || !mounted) return;
      final me = jsonDecode(meRes.body) as Map<String, dynamic>;
      final role = me['role']?.toString() ?? 'client';
      setState(() {
        _role = role;
        if (!_allowedContentTypes.contains(_contentType)) {
          _contentType = _allowedContentTypes.first;
        }
      });
    } catch (_) {
      // non-blocking
    }
  }

  Future<void> _loadRefs() async {
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) {
      return;
    }
    try {
      final stylesRes = await _api.getJson(
        '/catalogs/styles',
        accessToken: token,
        query: const {'lang': 'ru'},
      );
      final tagsRes = await _api.getJson(
        '/catalogs/tags',
        accessToken: token,
        query: const {'lang': 'ru'},
      );
      if (!mounted) return;
      final meRes = await _api.getJson('/profiles/me/full', accessToken: token);
      final ownerId = meRes.statusCode == 200
          ? (jsonDecode(meRes.body) as Map<String, dynamic>)['user_id']
                ?.toString()
          : null;
      final colRes = ownerId == null
          ? null
          : await _api.getJson(
              '/collections',
              accessToken: token,
              query: {'owner_id': ownerId},
            );

      if (stylesRes.statusCode == 200 && tagsRes.statusCode == 200) {
        setState(() {
          _styles = (jsonDecode(stylesRes.body) as List<dynamic>)
              .cast<Map<String, dynamic>>();
          _tags = (jsonDecode(tagsRes.body) as List<dynamic>)
              .cast<Map<String, dynamic>>();
          _collections = colRes != null && colRes.statusCode == 200
              ? (jsonDecode(colRes.body) as List<dynamic>)
                    .cast<Map<String, dynamic>>()
              : const [];
        });
      }
    } catch (_) {
      // optional
    }
  }

  Future<void> _pickImages() async {
    final picker = ImagePicker();
    final files = await picker.pickMultiImage();
    if (!mounted || files.isEmpty) return;
    setState(() => _pickedFiles = files);
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
    final localSelected = Set<String>.from(selectedIds);
    var query = '';
    final queryCtrl = TextEditingController();

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final filtered = _filteredCatalogItems(items, query);
            final locale = AppLocaleScope.of(context).locale;
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
                        fontFamily: AppTypography.headerFont(locale),
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
                                fontFamily: AppTypography.bodyFont(locale),
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

  String _contentTypeLabel(String value, bool isRu) {
    final ru = {
      'sketch': 'Скетч',
      'final_work': 'Финальная работа',
      'portfolio': 'Портфолио',
      'process': 'Процесс',
      'materials': 'Материалы',
      'find_us': 'Как нас найти',
      'achievments': 'Достижения',
    };
    final en = {
      'sketch': 'Sketch',
      'final_work': 'Final work',
      'portfolio': 'Portfolio',
      'process': 'Process',
      'materials': 'Materials',
      'find_us': 'How to find us',
      'achievments': 'Achievements',
    };
    return (isRu ? ru[value] : en[value]) ?? value;
  }

  Future<void> _createCustomTag() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) return;

    final ctrl = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isRu
              ? 'Новый тег'
              : 'New tag',
        ),
        content: TextField(
          controller: ctrl,
          decoration: InputDecoration(
            labelText: isRu
                ? 'Название тега'
                : 'Tag name',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(
              isRu ? 'Отмена' : 'Cancel',
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, ctrl.text.trim()),
            child: Text(
              isRu ? 'Создать' : 'Create',
            ),
          ),
        ],
      ),
    );

    if (value == null || value.isEmpty) return;

    final res = await _api.postJson('/catalogs/tags', {
      'name': value,
    }, accessToken: token);
    if (!mounted) return;
    if (res.statusCode != 201) {
      setState(
        () => _error =
            '${isRu ? 'Не удалось создать тег' : 'Failed to create tag'}: ${res.statusCode}',
      );
      return;
    }

    final tag = jsonDecode(res.body) as Map<String, dynamic>;
    final id = tag['id']?.toString();
    if (id == null || id.isEmpty) return;

    setState(() {
      _tags = [..._tags, tag];
      _selectedTagIds.add(id);
    });
  }

  Future<void> _submit() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final token = AppSession.instance.accessToken;
    if (token == null || token.isEmpty) {
      setState(
        () => _error = isRu
            ? 'Нужна авторизация в приложении.'
            : 'Authentication required.',
      );
      return;
    }

    if (_pickedFiles.isEmpty) {
      setState(
        () => _error = isRu
            ? 'Добавьте хотя бы одно изображение.'
            : 'Add at least one image.',
      );
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final mediaUrls = <String>[];
      final mediaItems = <Map<String, dynamic>>[];
      for (final file in _pickedFiles) {
        final uploadRes = await _api.postMultipart(
          '/sketches/upload-media',
          file: File(file.path),
          fieldName: 'file',
          accessToken: token,
        );
        if (uploadRes.statusCode != 200) {
          throw Exception('${uploadRes.statusCode}: ${uploadRes.body}');
        }
        final payload = jsonDecode(uploadRes.body) as Map<String, dynamic>;

        final url =
            payload['url']?.toString() ??
            payload['media_url']?.toString() ??
            payload['file_url']?.toString() ??
            payload['reference']?.toString();

        if (url == null || url.isEmpty) {
          throw Exception(
            'UPLOAD STATUS: ${uploadRes.statusCode}\n'
            'UPLOAD BODY: ${uploadRes.body}',
          );
        }
        mediaUrls.add(url);
        mediaItems.add({'url': url, 'phash': payload['phash']?.toString()});
      }

      final createRes = await _api.postJson('/sketches', {
        'title': _titleCtrl.text.trim().isEmpty ? null : _titleCtrl.text.trim(),
        'description': _descriptionCtrl.text.trim().isEmpty
            ? null
            : _descriptionCtrl.text.trim(),
        'content_type': _contentType,
        'feed_visibility': _isPublic ? 'public' : 'private',
        'media_urls': mediaUrls,
        'media_items': mediaItems,
        if (_selectedCollectionId != null)
          'collection_id': _selectedCollectionId,
      }, accessToken: token);

      if (createRes.statusCode != 201) {
        throw Exception('${createRes.statusCode}: ${createRes.body}');
      }

      final created = jsonDecode(createRes.body) as Map<String, dynamic>;
      final sketchId = created['id']?.toString();
      if (sketchId == null || sketchId.isEmpty) {
        throw Exception(
          isRu
              ? 'Пост создан, но сервер не вернул id.'
              : 'Created post id is missing.',
        );
      }

      if (_selectedStyleIds.isNotEmpty) {
        await _api.putJson('/sketches/$sketchId/styles', {
          'ids': _selectedStyleIds.toList(),
        }, accessToken: token);
      }
      if (_selectedTagIds.isNotEmpty) {
        await _api.putJson('/sketches/$sketchId/tags', {
          'ids': _selectedTagIds.toList(),
        }, accessToken: token);
      }

      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(
        () => _error =
            (isRu ? 'Ошибка создания поста: ' : 'Create post failed: ') +
            e.toString(),
      );
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        title: Text(
          isRu ? 'Создание поста' : 'Create post',
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_error != null)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.accent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.accent),
                  ),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      color: AppColors.accent,
                    ),
                  ),
                ),
              TextField(
                controller: _titleCtrl,
                decoration: InputDecoration(
                  labelText: isRu ? 'Название поста' : 'Post title',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _descriptionCtrl,
                minLines: 3,
                maxLines: 6,
                decoration: InputDecoration(
                  labelText: isRu ? 'Описание' : 'Description',
                ),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _contentType,
                decoration: InputDecoration(
                  labelText: isRu ? 'Тип работы' : 'Content type',
                ),
                items: _allowedContentTypes
                    .map(
                      (value) => DropdownMenuItem(
                        value: value,
                        child: Text(_contentTypeLabel(value, isRu)),
                      ),
                    )
                    .toList(),
                onChanged: (v) {
                  if (v == null) return;
                  setState(() => _contentType = v);
                },
              ),
              const SizedBox(height: 8),
              if (_contentType == 'sketch' || _contentType == 'final_work')
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: _selectedCollectionId ?? '',
                  decoration: InputDecoration(
                    labelText: isRu
                        ? 'Коллекция'
                        : 'Collection',
                    helperText: isRu
                        ? 'Если не выбрано, пост попадет в коллекцию "Мои посты"'
                        : 'If empty, post goes to "My posts"',
                  ),
                  items: [
                    DropdownMenuItem<String>(
                      value: '',
                      child: Text(
                        isRu
                            ? 'Мои посты (по умолчанию)'
                            : 'My posts (default)',
                      ),
                    ),
                    ..._collections
                        .where(
                          (c) =>
                              (c['collection_type']?.toString() ?? '') ==
                              'custom',
                        )
                        .map(
                          (c) => DropdownMenuItem<String>(
                            value: c['id']?.toString(),
                            child: Text(c['title']?.toString() ?? ''),
                          ),
                        ),
                  ],
                  onChanged: (value) => setState(
                    () => _selectedCollectionId =
                        (value == null || value.isEmpty) ? null : value,
                  ),
                ),
              const SizedBox(height: 8),
              SwitchListTile.adaptive(
                value: _isPublic,
                contentPadding: EdgeInsets.zero,
                title: Text(
                  isRu ? 'Публичный пост' : 'Public post',
                  style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
                ),
                onChanged: (v) => setState(() => _isPublic = v),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _loading ? null : _pickImages,
                icon: const Icon(Icons.photo_library_outlined),
                label: Text(isRu ? 'Добавить изображение' : 'Add image'),
              ),
              if (_pickedFiles.isNotEmpty) ...[
                const SizedBox(height: 10),
                SizedBox(
                  height: 90,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _pickedFiles.length,
                    separatorBuilder: (_, index) => const SizedBox(width: 8),
                    itemBuilder: (context, index) => ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.file(
                        File(_pickedFiles[index].path),
                        width: 90,
                        height: 90,
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _loading
                          ? null
                          : () => _openCatalogPicker(
                              titleRu: 'Выберите стили',
                              titleEn: 'Pick styles',
                              items: _styles,
                              selectedIds: _selectedStyleIds,
                              isRu: isRu,
                              selectedColor: AppColors.accent,
                              onApply: (selected) {
                                setState(() {
                                  _selectedStyleIds
                                    ..clear()
                                    ..addAll(selected);
                                });
                              },
                            ),
                      icon: const Icon(Icons.style_outlined),
                      label: Text(
                        isRu
                            ? 'Стили (${_selectedStyleIds.length})'
                            : 'Styles (${_selectedStyleIds.length})',
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _loading
                          ? null
                          : () => _openCatalogPicker(
                              titleRu: 'Выберите теги',
                              titleEn: 'Pick tags',
                              items: _tags,
                              selectedIds: _selectedTagIds,
                              isRu: isRu,
                              selectedColor: AppColors.ink,
                              onApply: (selected) {
                                setState(() {
                                  _selectedTagIds
                                    ..clear()
                                    ..addAll(selected);
                                });
                              },
                            ),
                      icon: const Icon(Icons.label_outlined),
                      label: Text(
                        isRu
                            ? 'Теги (${_selectedTagIds.length})'
                            : 'Tags (${_selectedTagIds.length})',
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  TextButton.icon(
                    onPressed: _loading ? null : _createCustomTag,
                    icon: const Icon(Icons.add),
                    label: Text(
                      isRu
                          ? 'Свой тег'
                          : 'Custom tag',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(
                          isRu ? 'Опубликовать пост' : 'Publish post',
                          style: TextStyle(
                            fontFamily: AppTypography.bodyFont(locale),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
