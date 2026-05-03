import 'dart:convert';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'complaint_form_screen.dart';
import 'post_demo_screen.dart';

class ChatRoomScreenArgs {
  const ChatRoomScreenArgs({
    required this.chatId,
    this.peerUserId,
    this.peerNickname,
  });

  final String chatId;
  final String? peerUserId;
  final String? peerNickname;
}

class ChatRoomScreen extends StatefulWidget {
  const ChatRoomScreen({super.key});

  static const route = '/chat-room';

  @override
  State<ChatRoomScreen> createState() => _ChatRoomScreenState();
}

class _ChatRoomScreenState extends State<ChatRoomScreen> {
  final _api = ApiClient.defaultClient();
  final _messageCtrl = TextEditingController();
  final _picker = ImagePicker();
  final _scrollCtrl = ScrollController();

  bool _loading = true;
  bool _sending = false;
  String? _error;
  List<Map<String, dynamic>> _messages = const [];
  String? _peerNickname;
  String? _peerAvatarUrl;

  String? get _token => AppSession.instance.accessToken;

  ChatRoomScreenArgs get _args {
    final raw = ModalRoute.of(context)?.settings.arguments;
    return raw as ChatRoomScreenArgs;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _peerNickname = _args.peerNickname;
      _loadPeerHeader();
      _loadMessages();
    });
  }

  @override
  void dispose() {
    _messageCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadPeerHeader() async {
    final peerUserId = _args.peerUserId;
    if (_token == null || _token!.isEmpty) {
      return;
    }

    try {
      if (peerUserId != null && peerUserId.isNotEmpty) {
        final res = await _api.getJson(
          '/profiles/$peerUserId/full',
          accessToken: _token,
        );
        if (!mounted || res.statusCode != 200) return;

        final data = jsonDecode(res.body) as Map<String, dynamic>;
        setState(() {
          _peerNickname = data['nickname']?.toString() ?? _peerNickname;
          _peerAvatarUrl = data['avatar_url']?.toString();
        });
        return;
      }

      final chatsRes = await _api.getJson('/chats', accessToken: _token);
      if (!mounted || chatsRes.statusCode != 200) return;
      final chats = (jsonDecode(chatsRes.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final chat = chats.firstWhere(
        (c) => c['id']?.toString() == _args.chatId,
        orElse: () => const <String, dynamic>{},
      );
      if (chat.isNotEmpty) {
        setState(() {
          _peerNickname = chat['other_nickname']?.toString() ?? _peerNickname;
        });
      }
    } catch (_) {
      // optional chat header enrichment
    }
  }

  Future<void> _loadMessages() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _loading = false;
        _error =
            'Необходима авторизация';
      });
      return;
    }

    try {
      final res = await _api.getJson(
        '/chats/${_args.chatId}/messages',
        accessToken: _token,
        query: const {'limit': '200', 'offset': '0'},
      );

      if (!mounted) {
        return;
      }
      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback:
                'Не удалось загрузить сообщения',
          );
        });
        return;
      }

      final data = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => e as Map<String, dynamic>)
          .toList()
          .reversed
          .toList();

      setState(() {
        _messages = data;
        _loading = false;
      });

      _scrollToBottom();
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

  Future<void> _sendMessage() async {
    final text = _messageCtrl.text.trim();
    if (text.isEmpty || _sending) {
      return;
    }

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _error =
            'Необходима авторизация';
      });
      return;
    }

    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      final res = await _api.postJson('/chats/${_args.chatId}/messages', {
        'text': text,
      }, accessToken: _token);

      if (!mounted) {
        return;
      }

      if (res.statusCode != 201) {
        setState(() {
          _sending = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback:
                'Не удалось загрузить сообщения',
          );
        });
        return;
      }

      final message = jsonDecode(res.body) as Map<String, dynamic>;
      _messageCtrl.clear();
      setState(() {
        _messages = [..._messages, message];
        _sending = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _sending = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _pickAndSendImage() async {
    final file = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 90,
    );
    if (file == null) return;
    await _sendFile(file.path);
  }

  Future<void> _pickAndSendFile() async {
    final picked = await FilePicker.platform.pickFiles(withData: false);
    if (picked == null || picked.files.isEmpty) return;
    final filePath = picked.files.single.path;
    if (filePath == null || filePath.isEmpty) return;
    await _sendFile(filePath);
  }

  Future<void> _sendFile(String filePath) async {
    if (_sending) return;

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _error =
            'Необходима авторизация';
      });
      return;
    }

    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      final uri = Uri.parse(
        '${_api.baseUrl}/chats/${_args.chatId}/messages/with-file',
      );
      final textPayload = _messageCtrl.text.trim();
      final req = http.MultipartRequest('POST', uri)
        ..headers['Authorization'] = 'Bearer ${_token!}'
        ..fields['text'] = textPayload
        ..files.add(
          await http.MultipartFile.fromPath(
            'file',
            filePath,
            filename: Uri.file(filePath).pathSegments.isEmpty
                ? 'file'
                : Uri.file(filePath).pathSegments.last,
          ),
        );

      final streamed = await req.send();
      final body = await streamed.stream.bytesToString();

      if (!mounted) return;

      if (streamed.statusCode != 201) {
        setState(() {
          _sending = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            streamed.statusCode,
            body,
            fallback:
                'Не удалось отправить файл',
          );
        });
        return;
      }

      final message = jsonDecode(body) as Map<String, dynamic>;
      setState(() {
        _messages = [..._messages, message];
        _sending = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _confirmInkmatch(String inkmatchId) async {
    if (_token == null || _token!.isEmpty) {
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      final res = await _api.postJson(
        '/chats/${_args.chatId}/inkmatch/$inkmatchId/confirm',
        const {},
        accessToken: _token,
      );

      if (!mounted) {
        return;
      }

      if (res.statusCode != 200) {
        setState(() {
          _sending = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback:
                'Не удалось подтвердить запись',
          );
        });
        return;
      }

      setState(() {
        _sending = false;
      });
      await _loadMessages();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _sending = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _cancelInkmatch(String inkmatchId) async {
    if (_token == null || _token!.isEmpty) {
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      final res = await _api.postJson(
        '/chats/${_args.chatId}/inkmatch/$inkmatchId/cancel',
        const {},
        accessToken: _token,
      );

      if (!mounted) {
        return;
      }

      if (res.statusCode != 204) {
        setState(() {
          _sending = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback:
                'Не удалось отменить InkMatch',
          );
        });
        return;
      }

      setState(() {
        _sending = false;
      });
      await _loadMessages();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _sending = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _openMap(double lat, double lon) async {
    final uri = Uri.parse('geo:$lat,$lon?q=$lat,$lon');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
      return;
    }
    await launchUrl(
      Uri.parse('https://yandex.ru/maps/?pt=$lon,$lat&z=16&l=map'),
      mode: LaunchMode.externalApplication,
    );
  }

  Future<void> _leaveReview(String inkmatchId) async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    int rating = 5;
    final bodyCtrl = TextEditingController();
    final attachedImages = <XFile>[];

    final submit = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(
                isRu
                    ? 'Отзыв о сеансе'
                    : 'Session review',
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Text(
                          isRu
                              ? 'Оценка:'
                              : 'Rating:',
                        ),
                        const SizedBox(width: 8),
                        DropdownButton<int>(
                          value: rating,
                          items: const [1, 2, 3, 4, 5]
                              .map(
                                (e) => DropdownMenuItem(
                                  value: e,
                                  child: Text('$e'),
                                ),
                              )
                              .toList(),
                          onChanged: (v) {
                            if (v == null) return;
                            setDialogState(() => rating = v);
                          },
                        ),
                      ],
                    ),
                    TextField(
                      controller: bodyCtrl,
                      maxLines: 3,
                      decoration: InputDecoration(
                        hintText: isRu
                            ? 'Комментарий (необязательно)'
                            : 'Comment (optional)',
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.photo_library_outlined),
                        label: Text(
                          isRu
                              ? 'Добавить фото результата (${attachedImages.length})'
                              : 'Attach result photos (${attachedImages.length})',
                        ),
                        onPressed: () async {
                          final images = await _picker.pickMultiImage();
                          if (images.isEmpty) return;
                          setDialogState(() {
                            attachedImages
                              ..clear()
                              ..addAll(images);
                          });
                        },
                      ),
                    ),
                  ],
                ),
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
                    isRu
                        ? 'Отправить'
                        : 'Submit',
                  ),
                ),
              ],
            );
          },
        );
      },
    );

    if (submit != true || _token == null || _token!.isEmpty) {
      return;
    }

    setState(() {
      _sending = true;
      _error = null;
    });

    try {
      final res = await _api.postJson('/inkmatch/reviews', {
        'inkmatch_id': inkmatchId,
        'rating_overall': rating,
        'rating_communication': rating,
        'rating_cleanliness': rating,
        'rating_quality': rating,
        'rating_punctuality': rating,
        'rating_price_fairness': rating,
        'body': bodyCtrl.text.trim().isEmpty ? null : bodyCtrl.text.trim(),
      }, accessToken: _token);
      if (!mounted) return;

      if (res.statusCode != 201) {
        setState(() {
          _sending = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: isRu
                ? 'Не удалось отправить отзыв'
                : 'Failed to submit review',
          );
        });
        return;
      }

      final review = jsonDecode(res.body) as Map<String, dynamic>;
      final reviewId = review['id']?.toString();

      if (reviewId != null &&
          reviewId.isNotEmpty &&
          attachedImages.isNotEmpty) {
        for (final img in attachedImages) {
          final uploadRes = await _api.postMultipart(
            '/sketches/upload-media',
            file: File(img.path),
            fieldName: 'file',
            accessToken: _token,
          );
          if (uploadRes.statusCode != 200) {
            continue;
          }
          final uploadPayload =
              jsonDecode(uploadRes.body) as Map<String, dynamic>;
          final fileUrl = uploadPayload['url']?.toString();
          if (fileUrl == null || fileUrl.isEmpty) {
            continue;
          }

          await _api.postJson('/inkmatch/reviews/$reviewId/attachments', {
            'file_url': fileUrl,
            'file_type': 'image',
          }, accessToken: _token);
        }
      }

      setState(() {
        _sending = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isRu
                ? 'Отзыв отправлен'
                : 'Review submitted',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
    }
  }

  Future<void> _openMessageComplaint(Map<String, dynamic> message) async {
    final messageId = message['id']?.toString();
    if (messageId == null || messageId.isEmpty) {
      return;
    }
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: ListTile(
          leading: const Icon(Icons.flag_outlined),
          title: Text(isRu ? 'Пожаловаться на сообщение' : 'Report message'),
          onTap: () {
            Navigator.pop(context);
            Navigator.pushNamed(
              this.context,
              ComplaintFormScreen.route,
              arguments: ComplaintFormArgs(
                targetType: 'message',
                targetId: messageId,
                targetTitle: isRu ? 'Сообщение в чате' : 'Chat message',
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildAttachments(List<dynamic> attachments, bool mine) {
    if (attachments.isEmpty) return const SizedBox.shrink();

    bool isImageAttachment(Map<String, dynamic> item) {
      final fileType = item['file_type']?.toString() ?? '';
      final mime = item['mime_type']?.toString().toLowerCase() ?? '';
      final url = item['file_url']?.toString().toLowerCase() ?? '';
      return fileType == 'image' ||
          mime.startsWith('image/') ||
          url.endsWith('.jpg') ||
          url.endsWith('.jpeg') ||
          url.endsWith('.png') ||
          url.endsWith('.webp');
    }

    return Column(
      children: attachments.map((raw) {
        final item = raw as Map<String, dynamic>;
        final url = item['file_url']?.toString() ?? '';
        if (url.isEmpty) return const SizedBox.shrink();

        if (isImageAttachment(item)) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: GestureDetector(
              onTap: () => _downloadAttachment(url),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.network(
                  url,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) => Container(
                    height: 120,
                    color: Colors.black12,
                    child: const Center(child: Icon(Icons.broken_image)),
                  ),
                ),
              ),
            ),
          );
        }

        final name = Uri.tryParse(url)?.pathSegments.last ?? 'file';
        return Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: GestureDetector(
            onTap: () => _downloadAttachment(url),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: (mine ? Colors.white : AppColors.accent).withValues(
                  alpha: 0.15,
                ),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.insert_drive_file_outlined,
                    size: 18,
                    color: Colors.white,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white),
                    ),
                  ),
                  const Icon(Icons.download, color: Colors.white, size: 18),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Future<void> _downloadAttachment(String url) async {
    final isRu = AppLocaleScope.of(context).locale.languageCode == 'ru';
    try {
      final res = await http.get(Uri.parse(url));
      if (res.statusCode != 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              isRu
                  ? 'Ошибка загрузки: ${res.statusCode}'
                  : 'Download failed: ${res.statusCode}',
            ),
          ),
        );
        return;
      }

      final uri = Uri.parse(url);
      final rawName = uri.pathSegments.isNotEmpty
          ? uri.pathSegments.last
          : 'file';
      final fileName = rawName.isEmpty ? 'file' : rawName;

      Directory? targetDir;
      if (Platform.isAndroid) {
        final publicDownload = Directory(
          '/storage/emulated/0/Download/InkMatch',
        );
        try {
          await publicDownload.create(recursive: true);
          targetDir = publicDownload;
        } catch (_) {
          targetDir = null;
        }
      }

      if (targetDir == null) {
        try {
          targetDir = await getDownloadsDirectory();
        } catch (_) {
          targetDir = null;
        }
      }
      targetDir ??= await getApplicationDocumentsDirectory();

      final saveDir = targetDir.path.endsWith('InkMatch')
          ? targetDir
          : Directory('${targetDir.path}/InkMatch');
      await saveDir.create(recursive: true);

      final file = File('${saveDir.path}/$fileName');
      await file.writeAsBytes(res.bodyBytes, flush: true);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          duration: const Duration(seconds: 6),
          content: Text(
            isRu ? 'Файл сохранен: ${file.path}' : 'File saved: ${file.path}',
          ),
          action: SnackBarAction(
            label: isRu ? 'Копировать путь' : 'Copy path',
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: file.path));
              if (!mounted) return;
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(isRu ? 'Путь скопирован' : 'Path copied'),
                ),
              );
            },
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(
        SnackBar(
          content: Text(isRu ? 'Ошибка скачивания: $e' : 'Download error: $e'),
        ),
      );
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) {
        return;
      }
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  bool _isMine(Map<String, dynamic> message) {
    final senderId = message['sender_id']?.toString();
    final token = _token;
    if (token == null ||
        token.isEmpty ||
        senderId == null ||
        senderId.isEmpty) {
      return false;
    }

    final parts = token.split('.');
    if (parts.length != 3) {
      return false;
    }

    try {
      final payload =
          jsonDecode(
                utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
              )
              as Map<String, dynamic>;
      final currentUserId = payload['sub']?.toString();
      return currentUserId == senderId;
    } catch (_) {
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';
    final title = (_peerNickname == null || _peerNickname!.isEmpty)
        ? (isRu ? 'Чат' : 'Chat')
        : _peerNickname!;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.ink,
        titleSpacing: 0,
        title: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: AppColors.ink,
              backgroundImage:
                  (_peerAvatarUrl != null && _peerAvatarUrl!.isNotEmpty)
                  ? NetworkImage(_peerAvatarUrl!)
                  : null,
              child: (_peerAvatarUrl == null || _peerAvatarUrl!.isEmpty)
                  ? const Icon(Icons.person, color: Colors.white, size: 18)
                  : null,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontFamily: AppTypography.headerFont(locale),
                  color: AppColors.ink,
                ),
              ),
            ),
          ],
        ),
      ),
      backgroundColor: AppColors.background,
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              color: Colors.red.withValues(alpha: 0.08),
              padding: const EdgeInsets.all(10),
              child: Text(
                _error!,
                style: TextStyle(
                  color: Colors.red.shade900,
                  fontFamily: AppTypography.bodyFont(locale),
                ),
                textAlign: TextAlign.center,
              ),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
                    onRefresh: _loadMessages,
                    child: ListView.builder(
                      controller: _scrollCtrl,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 12,
                      ),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final message = _messages[index];
                        final mine = _isMine(message);
                        final text = message['text']?.toString() ?? '';
                        final attachments =
                            (message['attachments'] as List<dynamic>? ??
                            const []);
                        final messageType =
                            message['message_type']?.toString() ?? 'text';
                        final payload = message['payload'];

                        if (messageType == 'system_inkmatch') {
                          final payloadMap = payload is Map<String, dynamic>
                              ? payload
                              : const <String, dynamic>{};
                          final matchId = payloadMap['inkmatch_id']?.toString();
                          final effectiveMatchId =
                              (matchId == null || matchId.isEmpty)
                              ? 'none'
                              : matchId;
                          final action = payloadMap['action']?.toString() ?? '';
                          final isClient =
                              AppSession.instance.role ==
                              SessionUserRole.client;

                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: AppColors.ink.withValues(alpha: 0.2),
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  text,
                                  style: TextStyle(
                                    fontFamily: AppTypography.bodyFont(locale),
                                    color: AppColors.ink,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                if (payloadMap['sketch_preview_url'] !=
                                    null) ...[
                                  const SizedBox(height: 8),
                                  InkWell(
                                    borderRadius: BorderRadius.circular(10),
                                    onTap: () {
                                      final sketchId = payloadMap['sketch_id']
                                          ?.toString();
                                      if (sketchId == null || sketchId.isEmpty)
                                        return;
                                      Navigator.pushNamed(
                                        context,
                                        PostDemoScreen.route,
                                        arguments: sketchId,
                                      );
                                    },
                                    child: ClipRRect(
                                      borderRadius: BorderRadius.circular(10),
                                      child: Image.network(
                                        payloadMap['sketch_preview_url']
                                            .toString(),
                                        height: 140,
                                        width: double.infinity,
                                        fit: BoxFit.cover,
                                        errorBuilder: (_, __, ___) => Container(
                                          height: 120,
                                          color: Colors.black12,
                                          child: const Center(
                                            child: Icon(Icons.broken_image),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                                if (payloadMap['offer_price'] != null ||
                                    payloadMap['offer_duration_minutes'] !=
                                        null) ...[
                                  const SizedBox(height: 8),
                                  Text(
                                    isRu
                                        ? 'Цена мастера: ${payloadMap['offer_price'] ?? '-'} ₽ | Длительность: ${payloadMap['offer_duration_minutes'] ?? '-'} мин'
                                        : 'Master offer: ${payloadMap['offer_price'] ?? '-'} RUB | Duration: ${payloadMap['offer_duration_minutes'] ?? '-'} min',
                                    style: TextStyle(
                                      fontFamily: AppTypography.bodyFont(
                                        locale,
                                      ),
                                      color: AppColors.ink,
                                    ),
                                  ),
                                ],
                                if (payloadMap['master_location']
                                    is Map<String, dynamic>) ...[
                                  const SizedBox(height: 8),
                                  Builder(
                                    builder: (context) {
                                      final loc =
                                          payloadMap['master_location']
                                              as Map<String, dynamic>;
                                      final lat = (loc['lat'] as num?)
                                          ?.toDouble();
                                      final lon = (loc['lon'] as num?)
                                          ?.toDouble();
                                      return OutlinedButton.icon(
                                        onPressed: lat == null || lon == null
                                            ? null
                                            : () => _openMap(lat, lon),
                                        icon: const Icon(Icons.map_outlined),
                                        label: Align(
                                          alignment: Alignment.centerLeft,
                                          child: Text(
                                            loc['address']?.toString() ??
                                                (isRu
                                                    ? 'Адрес студии мастера'
                                                    : 'Master studio address'),
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                                ],
                                if (action == '' ||
                                    action == 'match_created' ||
                                    action == 'one_side_confirmed') ...[
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: ElevatedButton(
                                          onPressed: _sending
                                              ? null
                                              : () => _confirmInkmatch(
                                                  effectiveMatchId,
                                                ),
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: AppColors.accent,
                                            foregroundColor: Colors.white,
                                          ),
                                          child: Text(
                                            isRu
                                                ? 'Подтвердить запись'
                                                : 'Confirm booking',
                                            style: TextStyle(
                                              fontFamily:
                                                  AppTypography.bodyFont(
                                                    locale,
                                                  ),
                                              fontSize: 12,
                                            ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: OutlinedButton(
                                          onPressed: _sending
                                              ? null
                                              : () => _cancelInkmatch(
                                                  effectiveMatchId,
                                                ),
                                          child: Text(
                                            isRu ? 'Отмена' : 'Cancel',
                                            style: TextStyle(
                                              fontFamily:
                                                  AppTypography.bodyFont(
                                                    locale,
                                                  ),
                                              fontSize: 12,
                                            ),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                                if (action == 'both_confirmed' && isClient) ...[
                                  const SizedBox(height: 8),
                                  SizedBox(
                                    width: double.infinity,
                                    child: OutlinedButton(
                                      onPressed: _sending
                                          ? null
                                          : () =>
                                                _leaveReview(effectiveMatchId),
                                      child: Text(
                                        isRu
                                            ? 'Оставить отзыв о сеансе'
                                            : 'Leave session review',
                                        style: TextStyle(
                                          fontFamily: AppTypography.bodyFont(
                                            locale,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          );
                        }

                        final rawStatus = message['message_status']?.toString();
                        final messageStatus = rawStatus == null
                            ? null
                            : (isRu
                                  ? (rawStatus == 'read'
                                        ? 'Прочитано'
                                        : rawStatus == 'delivered'
                                        ? 'Доставлено'
                                        : 'Отправлено')
                                  : rawStatus);
                        return GestureDetector(
                          onLongPress: () => _openMessageComplaint(message),
                          child: Align(
                            alignment: mine
                                ? Alignment.centerRight
                                : Alignment.centerLeft,
                            child: Container(
                              constraints: const BoxConstraints(maxWidth: 280),
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 10,
                              ),
                              decoration: BoxDecoration(
                                color: mine ? AppColors.accent : AppColors.ink,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  if (attachments.isNotEmpty)
                                    _buildAttachments(attachments, mine),
                                  if (text.isNotEmpty)
                                    Align(
                                      alignment: Alignment.centerLeft,
                                      child: Text(
                                        text,
                                        style: TextStyle(
                                          fontFamily: AppTypography.bodyFont(
                                            locale,
                                          ),
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                  if (mine && messageStatus != null)
                                    Text(
                                      messageStatus,
                                      style: TextStyle(
                                        fontFamily: AppTypography.bodyFont(
                                          locale,
                                        ),
                                        color: Colors.white.withValues(
                                          alpha: 0.85,
                                        ),
                                        fontSize: 11,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(10, 6, 10, 10),
              child: Row(
                children: [
                  IconButton(
                    onPressed: _sending ? null : _pickAndSendImage,
                    icon: const Icon(Icons.image_outlined),
                  ),
                  IconButton(
                    onPressed: _sending ? null : _pickAndSendFile,
                    icon: const Icon(Icons.attach_file),
                  ),
                  Expanded(
                    child: TextField(
                      controller: _messageCtrl,
                      maxLines: 4,
                      minLines: 1,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendMessage(),
                      decoration: InputDecoration(
                        hintText: isRu ? 'Введите сообщение' : 'Type a message',
                        hintStyle: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                        ),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accent,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(52, 52),
                    ),
                    onPressed: _sending ? null : _sendMessage,
                    child: _sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
