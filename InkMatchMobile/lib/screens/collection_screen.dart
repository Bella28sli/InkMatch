import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'post_demo_screen.dart';

class CollectionScreenArgs {
  const CollectionScreenArgs({
    required this.collectionId,
    required this.isOwner,
  });

  final String collectionId;
  final bool isOwner;
}

class CollectionScreen extends StatefulWidget {
  const CollectionScreen({super.key});

  static const route = '/collection';

  @override
  State<CollectionScreen> createState() => _CollectionScreenState();
}

class _CollectionScreenState extends State<CollectionScreen> {
  final _api = ApiClient.defaultClient();

  bool _loading = true;
  String? _error;
  bool _actionBusy = false;

  String _id = '';
  String _title = '';
  String _description = '';
  bool _isPrivate = false;
  bool _isSystem = false;
  bool _canEdit = false;
  List<Map<String, dynamic>> _items = const [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_id.isNotEmpty) return;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is! CollectionScreenArgs) {
      setState(() {
        _loading = false;
        _error = 'Invalid collection args';
      });
      return;
    }
    _id = args.collectionId;
    _canEdit = args.isOwner;
    _loadCollection();
  }

  Future<void> _loadCollection() async {
    try {
      final res = await _api.getJson(
        '/collections/$_id',
        accessToken: AppSession.instance.accessToken,
      );
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${res.statusCode}: ${res.body}';
        });
        return;
      }
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final items = (data['items'] as List<dynamic>? ?? const [])
          .map((e) => (e as Map<String, dynamic>))
          .toList();

      setState(() {
        _title = (data['title'] ?? '').toString();
        _description = (data['description'] ?? '').toString();
        _isPrivate = (data['is_private'] ?? false) == true;
        _isSystem = (data['is_system'] ?? false) == true;
        _canEdit = (data['can_edit'] ?? _canEdit) == true;
        _items = items;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _shareCollection() async {
    if (_actionBusy) return;
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    setState(() => _actionBusy = true);
    try {
      final res = await _api.postJson(
        '/collections/$_id/share',
        {},
        accessToken: AppSession.instance.accessToken,
      );
      if (res.statusCode == 200) {
        final payload = jsonDecode(res.body) as Map<String, dynamic>;
        final url = payload['share_url']?.toString() ?? '';
        await Clipboard.setData(ClipboardData(text: url));
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              isRu
                  ? 'Ссылка скопирована: $url'
                  : 'Link copied: $url',
            ),
          ),
        );
      } else {
        _showError('${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      _showError('$e');
    } finally {
      if (mounted) setState(() => _actionBusy = false);
    }
  }

  Future<void> _removeItem(String sketchId) async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final res = await _api.deleteJson(
      '/collections/$_id/items/$sketchId',
      accessToken: AppSession.instance.accessToken,
    );
    if (res.statusCode == 204) {
      setState(() {
        _items = _items
            .where((e) => e['sketch_id']?.toString() != sketchId)
            .toList();
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isRu
                ? 'Элемент удален'
                : 'Item removed',
          ),
        ),
      );
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  Future<void> _editItemMetadata(Map<String, dynamic> item) async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final sketchId = item['sketch_id']?.toString() ?? '';
    if (sketchId.isEmpty) return;

    final durationCtrl = TextEditingController(text: item['work_duration_houres']?.toString() ?? '');
    final priceCtrl = TextEditingController(text: item['work_price']?.toString() ?? '');
    final currencyCtrl = TextEditingController(text: item['currency']?.toString() ?? 'RUB');
    final noteCtrl = TextEditingController(text: item['note']?.toString() ?? '');

    final payload = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(isRu ? 'Параметры работы' : 'Work details'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: durationCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: isRu ? 'Время работы, часов' : 'Duration, hours'),
              ),
              TextField(
                controller: priceCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: isRu ? 'Стоимость' : 'Price'),
              ),
              TextField(
                controller: currencyCtrl,
                decoration: InputDecoration(labelText: isRu ? 'Валюта' : 'Currency'),
              ),
              TextField(
                controller: noteCtrl,
                maxLines: 3,
                decoration: InputDecoration(labelText: isRu ? 'Комментарий к работе' : 'Work note'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, null),
            child: Text(isRu ? 'Отмена' : 'Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, {
              'work_duration_houres': int.tryParse(durationCtrl.text.trim()),
              'work_price': int.tryParse(priceCtrl.text.trim()),
              'currency': currencyCtrl.text.trim().isEmpty ? null : currencyCtrl.text.trim().toUpperCase(),
              'note': noteCtrl.text.trim().isEmpty ? null : noteCtrl.text.trim(),
            }),
            child: Text(isRu ? 'Сохранить' : 'Save'),
          ),
        ],
      ),
    );
    if (payload == null) return;

    final res = await _api.patchJson(
      '/collections/$_id/items/$sketchId',
      payload,
      accessToken: AppSession.instance.accessToken,
    );
    if (res.statusCode == 204) {
      await _loadCollection();
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  Future<void> _deleteCollection() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isRu
              ? 'Удалить коллекцию?'
              : 'Delete collection?',
        ),
        content: Text(
          isRu
              ? 'Это действие нельзя отменить.'
              : 'This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(
              isRu ? 'Отмена' : 'Cancel',
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(
              isRu ? 'Удалить' : 'Delete',
            ),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final res = await _api.deleteJson(
      '/collections/$_id',
      accessToken: AppSession.instance.accessToken,
    );
    if (res.statusCode == 204) {
      if (!mounted) return;
      Navigator.pop(context, true);
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        title: Text(
          isRu
              ? 'Коллекция'
              : 'Collection',
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _Header(
                  title: _valueOrEmpty(_title, isRu),
                  description: _valueOrEmpty(_description, isRu),
                  isRu: isRu,
                  isPrivate: _isPrivate,
                  isOwner: _canEdit,
                  actionBusy: _actionBusy,
                  onShare: _shareCollection,
                  onSettings: _openCollectionSettings,
                ),
                const SizedBox(height: 12),
                if (_items.isEmpty)
                  _EmptyCollection(isRu: isRu)
                else
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _items.length,
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 10,
                          mainAxisSpacing: 10,
                          childAspectRatio: 0.82,
                        ),
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      final imageUrl = item['media_url']?.toString();
                      final sketchId = item['sketch_id']?.toString() ?? '';
                      final metaLines = <String>[
                        if (item['work_duration_houres'] != null)
                          '${item['work_duration_houres']} ч',
                        if (item['work_price'] != null)
                          '${item['work_price']} ${item['currency'] ?? ''}'.trim(),
                        if ((item['note']?.toString().trim().isNotEmpty ??
                            false))
                          item['note'].toString(),
                      ];
                      return GestureDetector(
                        onTap: sketchId.isEmpty
                            ? null
                            : () => Navigator.pushNamed(
                                context,
                                PostDemoScreen.route,
                                arguments: sketchId,
                              ),
                        child: Stack(
                          children: [
                            Positioned.fill(
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(12),
                                child: imageUrl == null || imageUrl.isEmpty
                                    ? Container(
                                        color: AppColors.ink,
                                        child: const Icon(
                                          Icons.image_not_supported_outlined,
                                          color: Colors.white,
                                        ),
                                      )
                                    : Image.network(
                                        imageUrl,
                                        fit: BoxFit.cover,
                                        errorBuilder: (_, __, ___) => Container(
                                          color: AppColors.ink,
                                          child: const Icon(
                                            Icons.image_not_supported_outlined,
                                            color: Colors.white,
                                          ),
                                        ),
                                      ),
                              ),
                            ),
                            if (_canEdit && sketchId.isNotEmpty)
                              Positioned(
                                top: 6,
                                right: 6,
                                child: GestureDetector(
                                  onTap: () => _removeItem(sketchId),
                                  child: Container(
                                    padding: const EdgeInsets.all(6),
                                    decoration: BoxDecoration(
                                      color: AppColors.ink.withOpacity(0.75),
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: const Icon(
                                      Icons.close,
                                      color: Colors.white,
                                      size: 16,
                                    ),
                                  ),
                                ),
                              ),
                            if (_canEdit && sketchId.isNotEmpty)
                              Positioned(
                                top: 6,
                                left: 6,
                                child: GestureDetector(
                                  onTap: () => _editItemMetadata(item),
                                  child: Container(
                                    padding: const EdgeInsets.all(6),
                                    decoration: BoxDecoration(
                                      color: AppColors.ink.withOpacity(0.75),
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: const Icon(
                                      Icons.edit_outlined,
                                      color: Colors.white,
                                      size: 16,
                                    ),
                                  ),
                                ),
                              ),
                            if (metaLines.isNotEmpty)
                              Positioned(
                                left: 0,
                                right: 0,
                                bottom: 0,
                                child: Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: AppColors.ink.withOpacity(0.78),
                                    borderRadius: const BorderRadius.vertical(
                                      bottom: Radius.circular(12),
                                    ),
                                  ),
                                  child: Text(
                                    metaLines.join(' • '),
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontFamily:
                                          AppTypography.bodyFont(locale),
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
    );
  }

  void _openCollectionSettings() {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final titleController = TextEditingController(text: _title);
    final descriptionController = TextEditingController(text: _description);
    var privateValue = _isPrivate;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(context).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isRu
                        ? 'Настройки коллекции'
                        : 'Collection settings',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 22,
                      color: AppColors.ink,
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextFormField(
                    controller: titleController,
                    enabled: !_isSystem,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Название'
                          : 'Title',
                      helperText: _isSystem
                          ? (isRu
                                ? 'Для системной коллекции название не редактируется'
                                : 'Default collection title is locked')
                          : null,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: descriptionController,
                    maxLines: 3,
                    decoration: InputDecoration(
                      labelText: isRu
                          ? 'Описание'
                          : 'Description',
                    ),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: privateValue,
                    onChanged: (v) => setSheetState(() => privateValue = v),
                    title: Text(
                      isRu
                          ? 'Приватная коллекция'
                          : 'Private collection',
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () async {
                        final res = await _api.patchJson(
                          '/collections/$_id',
                          {
                            if (!_isSystem)
                              'title': titleController.text.trim(),
                            'description': descriptionController.text.trim(),
                            'is_private': privateValue,
                          },
                          accessToken: AppSession.instance.accessToken,
                        );
                        if (!mounted) return;
                        if (res.statusCode == 200) {
                          Navigator.pop(context);
                          _loadCollection();
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('${res.statusCode}: ${res.body}'),
                            ),
                          );
                        }
                      },
                      child: Text(
                        isRu
                            ? 'Сохранить'
                            : 'Save',
                      ),
                    ),
                  ),
                  if (_canEdit && !_isSystem) const SizedBox(height: 8),
                  if (_canEdit && !_isSystem)
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        onPressed: () {
                          Navigator.pop(context);
                          _deleteCollection();
                        },
                        child: Text(
                          isRu
                              ? 'Удалить коллекцию'
                              : 'Delete collection',
                        ),
                      ),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.title,
    required this.description,
    required this.isRu,
    required this.isPrivate,
    required this.isOwner,
    required this.actionBusy,
    required this.onShare,
    required this.onSettings,
  });

  final String title;
  final String description;
  final bool isRu;
  final bool isPrivate;
  final bool isOwner;
  final bool actionBusy;
  final VoidCallback onShare;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.78),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withOpacity(0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontFamily: AppTypography.headerFont(locale),
                    fontSize: 24,
                    color: AppColors.ink,
                  ),
                ),
              ),
              if (isPrivate)
                Container(
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.ink,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    isRu
                        ? 'Приватная'
                        : 'Private',
                    style: TextStyle(
                      color: AppColors.background,
                      fontFamily: AppTypography.bodyFont(locale),
                      fontSize: 12,
                    ),
                  ),
                ),
              IconButton(
                onPressed: actionBusy ? null : onShare,
                icon: const Icon(Icons.share_outlined),
              ),
              if (isOwner)
                IconButton(
                  onPressed: onSettings,
                  icon: const Icon(Icons.settings_outlined),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            description,
            style: TextStyle(
              fontFamily: AppTypography.bodyFont(locale),
              color: AppColors.ink,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyCollection extends StatelessWidget {
  const _EmptyCollection({required this.isRu});

  final bool isRu;

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.78),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withOpacity(0.15)),
      ),
      child: Text(
        isRu
            ? 'Здесь пока ничего нет'
            : 'Nothing here yet',
        style: TextStyle(
          fontFamily: AppTypography.bodyFont(locale),
          color: AppColors.ink,
        ),
      ),
    );
  }
}

String _valueOrEmpty(String value, bool isRu) {
  if (value.trim().isEmpty) {
    return isRu
        ? 'Здесь пока ничего нет'
        : 'Nothing here yet';
  }
  return value;
}
