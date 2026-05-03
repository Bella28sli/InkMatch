import 'dart:io';
import 'dart:typed_data';

import 'package:crop_your_image/crop_your_image.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

class AvatarPicker {
  AvatarPicker._();

  static final ImagePicker _picker = ImagePicker();

  static Future<File?> pickAndCrop(
    BuildContext context, {
    ImageSource source = ImageSource.gallery,
  }) async {
    try {
      final picked = await _picker.pickImage(
        source: source,
        imageQuality: 95,
        maxWidth: 2048,
      );
      if (picked == null) return null;

      final bytes = await picked.readAsBytes();
      if (!context.mounted) return null;
      return Navigator.push<File?>(
        context,
        MaterialPageRoute(
          fullscreenDialog: true,
          builder: (_) => _AvatarCropScreen(imageBytes: bytes),
        ),
      );
    } catch (_) {
      return null;
    }
  }

  static Future<ImageSource?> chooseSource(BuildContext context) async {
    return showModalBottomSheet<ImageSource>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('\u0412\u044b\u0431\u0440\u0430\u0442\u044c \u0438\u0437 \u0433\u0430\u043b\u0435\u0440\u0435\u0438'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined),
              title: const Text('\u0421\u0434\u0435\u043b\u0430\u0442\u044c \u0444\u043e\u0442\u043e'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
          ],
        ),
      ),
    );
  }
}

class _AvatarCropScreen extends StatefulWidget {
  const _AvatarCropScreen({required this.imageBytes});

  final Uint8List imageBytes;

  @override
  State<_AvatarCropScreen> createState() => _AvatarCropScreenState();
}

class _AvatarCropScreenState extends State<_AvatarCropScreen> {
  final _controller = CropController();
  bool _cropping = false;
  String? _error;

  Future<void> _saveCropped(Uint8List bytes) async {
    final dir = await getTemporaryDirectory();
    final file = File(
      '${dir.path}${Platform.pathSeparator}avatar_${DateTime.now().millisecondsSinceEpoch}.jpg',
    );
    await file.writeAsBytes(bytes, flush: true);
    if (mounted) Navigator.pop(context, file);
  }

  void _startCrop() {
    setState(() {
      _cropping = true;
      _error = null;
    });
    _controller.cropCircle();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: const Text('\u041e\u0431\u0440\u0435\u0437\u043a\u0430 \u0430\u0432\u0430\u0442\u0430\u0440\u0430'),
        actions: [
          TextButton(
            onPressed: _cropping ? null : _startCrop,
            child: const Text('\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c'),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Stack(
                children: [
                  Crop(
                    controller: _controller,
                    image: widget.imageBytes,
                    withCircleUi: true,
                    interactive: true,
                    aspectRatio: 1,
                    fixCropRect: true,
                    initialRectBuilder: (viewport, imageRect) {
                      final shortestSide =
                          viewport.width < viewport.height ? viewport.width : viewport.height;
                      final side = shortestSide * 0.78;
                      return Rect.fromCenter(
                        center: viewport.center,
                        width: side,
                        height: side,
                      );
                    },
                    onMoved: (_) => setState(() => _error = null),
                    willUpdateScale: (scale) => scale >= 1.0 && scale <= 6.0,
                    cornerDotBuilder: (size, edgeAlignment) => const SizedBox.shrink(),
                    onCropped: (croppedData) async {
                      await _saveCropped(croppedData);
                    },
                    onStatusChanged: (status) {
                      if (status == CropStatus.cropping) {
                        setState(() => _cropping = true);
                      }
                    },
                    maskColor: Colors.black.withValues(alpha: 0.65),
                    baseColor: Colors.black,
                  ),
                  if (_cropping)
                    Container(
                      color: Colors.black.withValues(alpha: 0.2),
                      child: const Center(
                        child: CircularProgressIndicator(color: Colors.white),
                      ),
                    ),
                ],
              ),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _cropping ? null : () => Navigator.pop(context),
                      child: const Text('\u041e\u0442\u043c\u0435\u043d\u0430'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _cropping ? null : _startCrop,
                      child: _cropping
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('\u041e\u0431\u0440\u0435\u0437\u0430\u0442\u044c'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
