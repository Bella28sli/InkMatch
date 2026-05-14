import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/app_session.dart';
import '../services/media_url_helper.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'inkmatch_create_screen.dart';
import 'complaint_form_screen.dart';
import 'profile_screen.dart';

class PostDemoScreen extends StatefulWidget {
  const PostDemoScreen({super.key});

  static const route = '/demo-post';

  @override
  State<PostDemoScreen> createState() => _PostDemoScreenState();
}

class _PostDemoScreenState extends State<PostDemoScreen> {
  final _api = ApiClient.defaultClient();
  final _commentCtrl = TextEditingController();

  bool _loading = true;
  bool _actionBusy = false;
  String? _error;
  Map<String, dynamic>? _post;
  List<Map<String, dynamic>> _comments = const [];
  List<Map<String, dynamic>> _similar = const [];
  bool _commentsExpanded = false;
  bool _descriptionExpanded = false;
  String? _replyToCommentId;
  String? _replyToNickname;
  String _postId = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_postId.isNotEmpty) return;
    final args = ModalRoute.of(context)?.settings.arguments;
    _postId = args?.toString() ?? '';
    if (_postId.isEmpty) {
      setState(() {
        _loading = false;
        _error = 'No post id';
      });
      return;
    }
    _load();
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final postRes = await _api.getJson(
        '/posts/$_postId',
        accessToken: AppSession.instance.accessToken,
      );
      final commentsRes = await _api.getJson(
        '/posts/$_postId/comments',
        accessToken: AppSession.instance.accessToken,
      );
      final similarRes = await _api.getJson(
        '/posts/$_postId/similar',
        accessToken: AppSession.instance.accessToken,
        query: {'limit': '24'},
      );

      if (postRes.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = '${postRes.statusCode}: ${postRes.body}';
        });
        return;
      }

      setState(() {
        _post = jsonDecode(postRes.body) as Map<String, dynamic>;
        _comments = commentsRes.statusCode == 200
            ? (jsonDecode(commentsRes.body) as List<dynamic>)
                  .cast<Map<String, dynamic>>()
            : [];
        _similar = similarRes.statusCode == 200
            ? (jsonDecode(similarRes.body) as List<dynamic>)
                  .map((e) => Map<String, dynamic>.from(e as Map))
                  .toList()
            : [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _toggleLike() async {
    if (_actionBusy || _post == null) return;
    setState(() => _actionBusy = true);
    try {
      final res = await _api.postJson(
        '/posts/$_postId/like-toggle',
        {},
        accessToken: AppSession.instance.accessToken,
      );
      if (res.statusCode == 200 && _post != null) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        setState(() {
          _post!['is_liked'] = data['is_liked'];
          _post!['like_amount'] = data['like_amount'];
        });
      }
    } finally {
      if (mounted) setState(() => _actionBusy = false);
    }
  }

  Future<void> _downloadImage() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final media = (_post?['media_urls'] as List<dynamic>? ?? const [])
        .map((e) => e.toString())
        .where((e) => e.isNotEmpty)
        .toList();
    final url = MediaUrlHelper.resolveUrl(media.isEmpty ? null : media.first);
    if (url == null) return;

    try {
      final response = await http.get(Uri.parse(url));
      if (response.statusCode != 200) {
        _showError('${response.statusCode}: ${response.reasonPhrase ?? 'download failed'}');
        return;
      }

      final dir = await _downloadDirectory();
      if (dir == null) {
        _showError(isRu ? 'Не удалось найти папку для загрузки' : 'No download folder found');
        return;
      }

      final fileName = 'inkmatch_$_postId${_guessExtension(url, response.headers['content-type'])}';
      final file = File('${dir.path}/$fileName');
      await file.writeAsBytes(response.bodyBytes);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isRu ? 'Фото сохранено' : 'Image saved',
          ),
        ),
      );
    } catch (e) {
      _showError('$e');
    }
  }

  Future<Directory?> _downloadDirectory() async {
    if (Platform.isAndroid) {
      final publicDownload = Directory('/storage/emulated/0/Download/InkMatch');
      try {
        await publicDownload.create(recursive: true);
        return publicDownload;
      } catch (_) {
        // fall through
      }
    }

    try {
      final downloads = await getDownloadsDirectory();
      if (downloads != null) {
        return Directory('${downloads.path}/InkMatch');
      }
    } catch (_) {
      // fall through
    }

    return getApplicationDocumentsDirectory();
  }

  String _guessExtension(String url, String? contentType) {
    final path = Uri.tryParse(url)?.path.toLowerCase() ?? '';
    if (path.endsWith('.png')) return '.png';
    if (path.endsWith('.webp')) return '.webp';
    if (path.endsWith('.gif')) return '.gif';
    if (path.endsWith('.jpg') || path.endsWith('.jpeg')) return '.jpg';
    final type = contentType?.toLowerCase() ?? '';
    if (type.contains('png')) return '.png';
    if (type.contains('webp')) return '.webp';
    if (type.contains('gif')) return '.gif';
    if (type.contains('jpeg') || type.contains('jpg')) return '.jpg';
    return '.jpg';
  }

  Future<void> _sendComment() async {
    final body = _commentCtrl.text.trim();
    if (body.isEmpty) return;

    final res = await _api.postJson('/posts/$_postId/comments', {
      'body': body,
      if (_replyToCommentId != null) 'parent_comment_id': _replyToCommentId,
    }, accessToken: AppSession.instance.accessToken);
    if (res.statusCode == 201 && _post != null) {
      final row = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() {
        _comments = [..._comments, row];
        _commentCtrl.clear();
        _replyToCommentId = null;
        _replyToNickname = null;
        _post!['comment_count'] = (_post!['comment_count'] ?? 0) + 1;
      });
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  Future<void> _openCollectionPicker() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    final meRes = await _api.getJson(
      '/profiles/me/full',
      accessToken: AppSession.instance.accessToken,
    );
    if (meRes.statusCode != 200) {
      _showError('${meRes.statusCode}: ${meRes.body}');
      return;
    }
    final me = jsonDecode(meRes.body) as Map<String, dynamic>;
    final ownerId = me['user_id']?.toString() ?? '';
    if (ownerId.isEmpty) return;

    final listRes = await _api.getJson(
      '/collections',
      accessToken: AppSession.instance.accessToken,
      query: {'owner_id': ownerId},
    );
    if (listRes.statusCode != 200) {
      _showError('${listRes.statusCode}: ${listRes.body}');
      return;
    }

    final collections = (jsonDecode(listRes.body) as List<dynamic>)
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    for (final c in collections) {
      final detailRes = await _api.getJson(
        '/collections/${c['id']}',
        accessToken: AppSession.instance.accessToken,
      );
      if (detailRes.statusCode != 200) {
        c['contains_post'] = false;
        continue;
      }
      final detail = jsonDecode(detailRes.body) as Map<String, dynamic>;
      final items = (detail['items'] as List<dynamic>? ?? const []);
      c['contains_post'] = items.any(
        (e) => (e as Map<String, dynamic>)['sketch_id']?.toString() == _postId,
      );
    }

    if (!mounted) return;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return SafeArea(
              child: Padding(
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
                      isRu ? 'Добавить в коллекцию' : 'Add to collection',
                      style: TextStyle(
                        fontFamily: AppTypography.headerFont(locale),
                        fontSize: 24,
                      ),
                    ),
                    const SizedBox(height: 10),
                    if (collections.isEmpty)
                      Text(isRu ? 'Здесь пока ничего нет' : 'Nothing here yet')
                    else
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 360),
                        child: ListView.separated(
                          shrinkWrap: true,
                          itemBuilder: (context, index) {
                            final c = collections[index];
                            final contains = c['contains_post'] == true;
                            return ListTile(
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                              tileColor: Colors.white,
                              title: Text(
                                c['title']?.toString() ?? '',
                                style: TextStyle(
                                  fontFamily: AppTypography.bodyFont(locale),
                                ),
                              ),
                              subtitle: Text(
                                (c['description']?.toString().isNotEmpty ??
                                        false)
                                    ? c['description'].toString()
                                    : (isRu ? 'Здесь пока ничего нет' : 'Nothing here yet'),
                                style: TextStyle(
                                  fontFamily: AppTypography.bodyFont(locale),
                                  fontSize: 12,
                                ),
                              ),
                              trailing: Icon(
                                contains
                                    ? Icons.check_circle
                                    : Icons.add_circle_outline,
                                color: contains
                                    ? AppColors.accent
                                    : AppColors.ink,
                              ),
                              onTap: () async {
                                final id = c['id']?.toString() ?? '';
                                if (id.isEmpty) return;
                                Map<String, dynamic> metadata = const {};
                                if (!contains &&
                                    c['collection_type']?.toString() ==
                                        'portfolio') {
                                  metadata =
                                      await _askPortfolioMetadata(isRu) ??
                                      const {};
                                }
                                final res = contains
                                    ? await _api.deleteJson(
                                        '/collections/$id/items/$_postId',
                                        accessToken:
                                            AppSession.instance.accessToken,
                                      )
                                    : await _api.postJson(
                                        '/collections/$id/items',
                                        {'sketch_id': _postId, ...metadata},
                                        accessToken:
                                            AppSession.instance.accessToken,
                                      );
                                if (res.statusCode == 204) {
                                  setSheetState(
                                    () => c['contains_post'] = !contains,
                                  );
                                } else {
                                  _showError('${res.statusCode}: ${res.body}');
                                }
                              },
                            );
                          },
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 8),
                          itemCount: collections.length,
                        ),
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


  Future<Map<String, dynamic>?> _askPortfolioMetadata(bool isRu) {
    final durationCtrl = TextEditingController();
    final priceCtrl = TextEditingController();
    final currencyCtrl = TextEditingController(text: 'RUB');
    final noteCtrl = TextEditingController();
    return showDialog<Map<String, dynamic>>(
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
                decoration: InputDecoration(
                  labelText: isRu ? 'Время работы, часов' : 'Duration, hours',
                ),
              ),
              TextField(
                controller: priceCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: isRu ? 'Стоимость' : 'Price',
                ),
              ),
              TextField(
                controller: currencyCtrl,
                decoration: InputDecoration(
                  labelText: isRu ? 'Валюта' : 'Currency',
                ),
              ),
              TextField(
                controller: noteCtrl,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: isRu ? 'Комментарий к работе' : 'Work note',
                ),
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
            onPressed: () {
              Navigator.pop(context, {
                if (int.tryParse(durationCtrl.text.trim()) != null)
                  'work_duration_houres': int.parse(durationCtrl.text.trim()),
                if (int.tryParse(priceCtrl.text.trim()) != null)
                  'work_price': int.parse(priceCtrl.text.trim()),
                if (currencyCtrl.text.trim().isNotEmpty)
                  'currency': currencyCtrl.text.trim().toUpperCase(),
                if (noteCtrl.text.trim().isNotEmpty)
                  'note': noteCtrl.text.trim(),
              });
            },
            child: Text(isRu ? 'Сохранить' : 'Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _deleteComment(Map<String, dynamic> comment) async {
    final id = comment['id']?.toString();
    if (id == null || id.isEmpty) return;
    final res = await _api.deleteJson(
      '/posts/comments/$id',
      accessToken: AppSession.instance.accessToken,
    );
    if (res.statusCode == 204) {
      setState(() {
        _comments = _comments.where((e) => e['id']?.toString() != id).toList();
        if (_post != null) {
          _post!['comment_count'] = (_post!['comment_count'] ?? 1) - 1;
        }
      });
    } else {
      _showError('${res.statusCode}: ${res.body}');
    }
  }

  void _startReply(Map<String, dynamic> comment) {
    setState(() {
      _replyToCommentId = comment['id']?.toString();
      _replyToNickname = comment['author_nickname']?.toString();
    });
  }

  void _cancelReply() {
    setState(() {
      _replyToCommentId = null;
      _replyToNickname = null;
    });
  }


  Future<void> _openComplaint({
    required String targetType,
    required String targetId,
    required String targetTitle,
  }) async {
    await Navigator.pushNamed(
      context,
      ComplaintFormScreen.route,
      arguments: ComplaintFormArgs(
        targetType: targetType,
        targetId: targetId,
        targetTitle: targetTitle,
      ),
    );
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  void _openPost(String postId) {
    if (postId.isEmpty) return;
    Navigator.pushNamed(context, PostDemoScreen.route, arguments: postId);
  }

  String? _currentUserId() {
    final token = AppSession.instance.accessToken;
    if (token == null) return null;
    final parts = token.split('.');
    if (parts.length < 2) return null;
    try {
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      ) as Map<String, dynamic>;
      return payload['sub']?.toString() ?? payload['user_id']?.toString();
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        title: Text(
          isRu ? 'Пост' : 'Post',
          style: TextStyle(fontFamily: AppTypography.headerFont(locale)),
        ),
        actions: [
          IconButton(
            onPressed: _post == null
                ? null
                : () => _openComplaint(
                      targetType: 'sketch',
                      targetId: _postId,
                      targetTitle: (_post!['title']?.toString().isNotEmpty ?? false)
                          ? _post!['title'].toString()
                          : '@${_post!['author_nickname']}',
                    ),
            icon: const Icon(Icons.flag_outlined),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : ListView(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
              children: [
                _mainMedia(),
                const SizedBox(height: 12),
                _postCard(isRu),
                const SizedBox(height: 10),
                _actions(isRu),
                const SizedBox(height: 12),
                _commentsBlock(isRu),
                const SizedBox(height: 16),
                _similarBlock(isRu),
              ],
            ),
    );
  }

  Widget _mainMedia() {
    final media = (_post!['media_urls'] as List<dynamic>).cast<String>();
    final url = MediaUrlHelper.resolveUrl(media.isEmpty ? null : media.first);
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: _mediaPreview(url, height: 340),
    );
  }

  Widget _mediaPreview(String? url, {required double height}) {
    if (url == null || url.isEmpty) {
      return Container(
        height: height,
        width: double.infinity,
        color: AppColors.ink,
        child: const Icon(Icons.image_not_supported, color: Colors.white),
      );
    }
    return Image.network(
      url,
      height: height,
      width: double.infinity,
      fit: BoxFit.cover,
      gaplessPlayback: true,
      loadingBuilder: (context, child, loadingProgress) {
        if (loadingProgress == null) return child;
        return Container(
          height: height,
          width: double.infinity,
          color: AppColors.ink.withValues(alpha: 0.08),
          alignment: Alignment.center,
          child: const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        );
      },
      errorBuilder: (_, __, ___) => Container(
        height: height,
        width: double.infinity,
        color: AppColors.ink,
        child: const Icon(Icons.broken_image, color: Colors.white),
      ),
    );
  }

  Widget _postCard(bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    final description = (_post?['description']?.toString() ?? '').trim();
    final styles = (_post?['styles'] as List<dynamic>? ?? const [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final tags = (_post?['tags'] as List<dynamic>? ?? const [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.9),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.ink.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            (_post!['title'] ?? (isRu ? 'Без названия' : 'Untitled'))
                .toString(),
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 24,
            ),
          ),
          if (description.isNotEmpty) ...[
            const SizedBox(height: 8),
            InkWell(
              onTap: () => setState(() => _descriptionExpanded = !_descriptionExpanded),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: AnimatedCrossFade(
                      firstChild: Text(
                        description,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                          color: AppColors.ink,
                        ),
                      ),
                      secondChild: Text(
                        description,
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                          color: AppColors.ink,
                        ),
                      ),
                      crossFadeState: _descriptionExpanded
                          ? CrossFadeState.showSecond
                          : CrossFadeState.showFirst,
                      duration: const Duration(milliseconds: 180),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    _descriptionExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 20,
                    color: AppColors.ink.withValues(alpha: 0.8),
                  ),
                ],
              ),
            ),
          ],
          if (styles.isNotEmpty || tags.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ...styles.map(
                  (item) => Chip(
                    label: Text(item['name']?.toString() ?? ''),
                    visualDensity: VisualDensity.compact,
                  ),
                ),
                ...tags.map(
                  (item) => Chip(
                    label: Text(item['name']?.toString() ?? ''),
                    visualDensity: VisualDensity.compact,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 8),
          InkWell(
            onTap: () => Navigator.pushNamed(
              context,
              ProfileScreen.route,
              arguments: ProfileScreenArgs(userId: _post!['author_id']?.toString()),
            ),
            child: Text(
              '@${_post!['author_nickname']}',
              style: TextStyle(
                fontFamily: AppTypography.bodyFont(locale),
                color: AppColors.accent,
                fontWeight: FontWeight.w700,
                decoration: TextDecoration.underline,
                decorationColor: AppColors.accent,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _actions(bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          onPressed: _actionBusy ? null : _toggleLike,
          icon: Icon(
            (_post!['is_liked'] ?? false)
                ? Icons.favorite
                : Icons.favorite_border,
          ),
          label: Text('${_post!['like_amount'] ?? 0}'),
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.accent,
            foregroundColor: Colors.white,
          ),
        ),
        OutlinedButton.icon(
          onPressed: _openCollectionPicker,
          icon: const Icon(Icons.collections_bookmark_outlined),
          label: Text(
            isRu ? 'В коллекцию' : 'To collections',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
        ),
        OutlinedButton.icon(
          onPressed: _downloadImage,
          icon: const Icon(Icons.download_outlined),
          label: Text(
            isRu ? 'Скачать' : 'Download',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
        ),
        FilledButton.icon(
          onPressed: _actionBusy
              ? null
              : () => Navigator.pushNamed(
                  context,
                  InkmatchCreateScreen.route,
                  arguments: InkmatchCreateScreenArgs(sketchId: _postId),
                ),
          icon: const Icon(Icons.bolt),
          label: Text(
            'InkMatch',
            style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
          ),
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.ink,
            foregroundColor: Colors.white,
          ),
        ),
      ],
    );
  }

  List<Map<String, dynamic>> _rootComments() {
    final ids = _comments.map((e) => e['id']?.toString()).whereType<String>().toSet();
    return _comments
        .where((c) {
          final parentId = c['parent_comment_id']?.toString();
          return parentId == null || parentId.isEmpty || !ids.contains(parentId);
        })
        .toList();
  }

  List<Map<String, dynamic>> _childComments(String parentId) {
    return _comments
        .where((c) => c['parent_comment_id']?.toString() == parentId)
        .toList();
  }

  Widget _commentThread(
    Map<String, dynamic> comment,
    bool isRu,
    Locale locale,
    int depth,
  ) {
    final children = _childComments(comment['id'].toString());
    final indent = depth == 0 ? 0.0 : 16.0;
    return Padding(
      padding: EdgeInsets.only(left: indent, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _commentRow(comment, isRu, locale),
          if (children.isNotEmpty)
            Padding(
              padding: EdgeInsets.only(left: depth >= 3 ? 8 : 6),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final child in children)
                    _commentThread(child, isRu, locale, depth + 1),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _commentRow(Map<String, dynamic> c, bool isRu, Locale locale) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Wrap(
            children: [
              GestureDetector(
                onTap: () => Navigator.pushNamed(
                  context,
                  ProfileScreen.route,
                  arguments: ProfileScreenArgs(userId: c['author_user_id']?.toString()),
                ),
                child: Text(
                  '@${c['author_nickname']}',
                  style: TextStyle(
                    fontFamily: AppTypography.bodyFont(locale),
                    color: AppColors.accent,
                    fontWeight: FontWeight.w700,
                    decoration: TextDecoration.underline,
                    decorationColor: AppColors.accent,
                  ),
                ),
              ),
              Text(
                ': ${c['body']}',
                style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: () => _openComplaint(
            targetType: 'comment',
            targetId: c['id'].toString(),
            targetTitle: isRu ? 'Комментарий' : 'Comment',
          ),
          icon: const Icon(Icons.flag_outlined, size: 18),
          visualDensity: VisualDensity.compact,
        ),
        IconButton(
          onPressed: () => _startReply(c),
          icon: const Icon(Icons.reply, size: 18),
          visualDensity: VisualDensity.compact,
        ),
        if (_post?['author_id']?.toString() == _currentUserId() ||
            c['author_user_id']?.toString() == _currentUserId())
          IconButton(
            onPressed: () => _deleteComment(c),
            icon: const Icon(Icons.delete_outline, size: 18),
            visualDensity: VisualDensity.compact,
          ),
      ],
    );
  }

  Widget _commentsBlock(bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    final roots = _rootComments();
    final visibleRoots = _commentsExpanded ? roots : roots.take(2).toList();
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.88),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.ink.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${isRu ? 'Комментарии' : 'Comments'} (${_post!['comment_count'] ?? 0})',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 20,
            ),
          ),
          const SizedBox(height: 8),
          if (_comments.isEmpty)
            Text(
              isRu ? 'Здесь пока ничего нет' : 'Nothing here yet',
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            )
          else ...[
            ...visibleRoots.map((c) => _commentThread(c, isRu, locale, 0)),
            if (roots.length > 2)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => setState(
                    () => _commentsExpanded = !_commentsExpanded,
                  ),
                  icon: Icon(
                    _commentsExpanded
                        ? Icons.expand_less
                        : Icons.expand_more,
                  ),
                  label: Text(
                    _commentsExpanded
                        ? (isRu ? 'Скрыть комментарии' : 'Hide comments')
                        : (isRu
                            ? 'Показать еще ${roots.length - 2}'
                            : 'Show ${roots.length - 2} more'),
                  ),
                ),
              ),
          ],
          if (_replyToCommentId != null)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.reply, size: 18),
              title: Text(isRu ? 'Ответить @$_replyToNickname' : 'Reply to @$_replyToNickname'),
              trailing: IconButton(
                onPressed: _cancelReply,
                icon: const Icon(Icons.close, size: 16),
              ),
            ),
          TextField(
            controller: _commentCtrl,
            decoration: InputDecoration(
              hintText: _replyToCommentId == null
                  ? (isRu ? 'Написать комментарий...' : 'Write a comment...')
                  : (isRu ? 'Написать ответ...' : 'Write a reply...'),
              suffixIcon: IconButton(
                onPressed: _sendComment,
                icon: const Icon(Icons.send),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _similarBlock(bool isRu) {
    final locale = AppLocaleScope.of(context).locale;
    if (_similar.isEmpty) {
      return const SizedBox.shrink();
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: Text(
            isRu ? 'Похожие эскизы' : 'Similar sketches',
            style: TextStyle(
              fontFamily: AppTypography.headerFont(locale),
              fontSize: 22,
              color: AppColors.ink,
            ),
          ),
        ),
        const SizedBox(height: 10),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: _similar.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 0.74,
          ),
          itemBuilder: (context, index) {
            final item = _similar[index];
            final imageUrl = item['image_url']?.toString();
            final postId = item['id']?.toString() ?? '';
            return InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: () => _openPost(postId),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (imageUrl == null || imageUrl.isEmpty)
                      Container(
                        color: AppColors.ink,
                        child: const Icon(Icons.image, color: Colors.white),
                      )
                    else
                      Image.network(
                        imageUrl,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          color: AppColors.ink,
                          child: const Icon(
                            Icons.broken_image,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        color: Colors.black.withValues(alpha: 0.45),
                        child: Text(
                          item['title']?.toString().isNotEmpty == true
                              ? item['title'].toString()
                              : '@${item['author_nickname'] ?? ''}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: Colors.white,
                            fontFamily: AppTypography.bodyFont(locale),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}
