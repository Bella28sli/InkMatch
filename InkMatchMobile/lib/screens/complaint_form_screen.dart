import 'dart:convert';

import 'package:flutter/material.dart';

import '../l10n/app_locale_scope.dart';
import '../services/api_client.dart';
import '../services/api_error_mapper.dart';
import '../services/app_session.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

class ComplaintFormArgs {
  const ComplaintFormArgs({
    required this.targetType,
    required this.targetId,
    this.targetTitle,
  });

  final String targetType;
  final String targetId;
  final String? targetTitle;
}

class ComplaintFormScreen extends StatefulWidget {
  const ComplaintFormScreen({super.key});

  static const route = '/complaints/new';

  @override
  State<ComplaintFormScreen> createState() => _ComplaintFormScreenState();
}

class _ComplaintFormScreenState extends State<ComplaintFormScreen> {
  final _api = ApiClient.defaultClient();
  final _detailsCtrl = TextEditingController();

  bool _loading = true;
  bool _submitting = false;
  String? _error;

  List<Map<String, dynamic>> _categories = const [];
  String? _selectedCategoryCode;
  String? _selectedReasonCode;

  String? get _token => AppSession.instance.accessToken;

  ComplaintFormArgs get _args =>
      ModalRoute.of(context)!.settings.arguments as ComplaintFormArgs;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadReasons());
  }

  @override
  void dispose() {
    _detailsCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadReasons() async {
    if (!mounted) return;
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
        '/complaints/reasons',
        accessToken: _token,
      );
      if (!mounted) return;

      if (res.statusCode != 200) {
        setState(() {
          _loading = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback:
                'Не удалось загрузить причины жалоб',
          );
        });
        return;
      }

      final payload = (jsonDecode(res.body) as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();

      String? categoryCode;
      String? reasonCode;
      if (payload.isNotEmpty) {
        categoryCode = payload.first['code']?.toString();
        final reasons = payload.first['reasons'] as List<dynamic>? ?? const [];
        if (reasons.isNotEmpty) {
          reasonCode = (reasons.first as Map<String, dynamic>)['code']
              ?.toString();
        }
      }

      setState(() {
        _categories = payload;
        _selectedCategoryCode = categoryCode;
        _selectedReasonCode = reasonCode;
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

  List<Map<String, dynamic>> get _selectedCategoryReasons {
    final category = _categories.firstWhere(
      (c) => c['code']?.toString() == _selectedCategoryCode,
      orElse: () => const <String, dynamic>{},
    );
    final reasons = category['reasons'];
    if (reasons is List<dynamic>) {
      return reasons.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return const [];
  }

  Future<void> _submit() async {
    final locale = AppLocaleScope.of(context).locale;
    final isRu = locale.languageCode == 'ru';

    if (_selectedReasonCode == null || _selectedReasonCode!.isEmpty) {
      setState(() {
        _error = isRu
            ? 'Выберите причину жалобы'
            : 'Select a complaint reason';
      });
      return;
    }

    if (_token == null || _token!.isEmpty) {
      setState(() {
        _error = isRu
            ? 'Необходима авторизация'
            : 'Not authenticated';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final res = await _api.postJson('/complaints', {
        'target_type': _args.targetType,
        'target_id': _args.targetId,
        'reason_code': _selectedReasonCode,
        'details': _detailsCtrl.text.trim().isEmpty
            ? null
            : _detailsCtrl.text.trim(),
      }, accessToken: _token);

      if (!mounted) return;

      if (res.statusCode != 201) {
        setState(() {
          _submitting = false;
          _error = ApiErrorMapper.mapHttpError(
            context,
            res.statusCode,
            res.body,
            fallback: isRu
                ? 'Не удалось отправить жалобу'
                : 'Failed to submit complaint',
          );
        });
        return;
      }

      setState(() {
        _submitting = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isRu
                ? 'Жалоба отправлена'
                : 'Complaint submitted',
          ),
        ),
      );
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = ApiErrorMapper.mapException(context, e);
      });
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
        foregroundColor: AppColors.ink,
        title: Text(
          isRu ? 'Жалоба' : 'Complaint',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            color: AppColors.ink,
          ),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_error != null)
                    Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.09),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: Colors.red.withValues(alpha: 0.22),
                        ),
                      ),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Colors.red.shade900,
                          fontFamily: AppTypography.bodyFont(locale),
                        ),
                      ),
                    ),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppColors.ink.withValues(alpha: 0.15),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isRu
                              ? 'Объект жалобы'
                              : 'Complaint target',
                          style: TextStyle(
                            fontFamily: AppTypography.headerFont(locale),
                            fontSize: 20,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _args.targetTitle ??
                              '${_args.targetType}: ${_args.targetId}',
                          style: TextStyle(
                            fontFamily: AppTypography.bodyFont(locale),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildCategorySelector(isRu, locale),
                  const SizedBox(height: 12),
                  _buildReasonSelector(isRu, locale),
                  const SizedBox(height: 12),
                  Text(
                    isRu
                        ? 'Комментарий (необязательно)'
                        : 'Comment (optional)',
                    style: TextStyle(
                      fontFamily: AppTypography.headerFont(locale),
                      fontSize: 18,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _detailsCtrl,
                    maxLines: 5,
                    maxLength: 4000,
                    decoration: InputDecoration(
                      hintText: isRu
                          ? 'Опишите детали, чтобы модератору было легче проверить жалобу'
                          : 'Add details to help moderation review your complaint',
                    ),
                  ),
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.accent,
                        foregroundColor: Colors.white,
                        minimumSize: const Size.fromHeight(50),
                      ),
                      onPressed: _submitting ? null : _submit,
                      icon: _submitting
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.flag_outlined),
                      label: Text(
                        isRu
                            ? 'Отправить жалобу'
                            : 'Submit complaint',
                        style: TextStyle(
                          fontFamily: AppTypography.bodyFont(locale),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildCategorySelector(bool isRu, Locale locale) {
    final items = _categories
        .map(
          (category) => DropdownMenuItem<String>(
            value: category['code']?.toString(),
            child: Text(
              category['title']?.toString() ?? '',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
          ),
        )
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          isRu
              ? 'Категория'
              : 'Category',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            fontSize: 18,
          ),
        ),
        const SizedBox(height: 6),
        DropdownButtonFormField<String>(
          isExpanded: true,
          icon: const Icon(Icons.arrow_drop_down),
          iconSize: 20,
          value: _selectedCategoryCode,
          menuMaxHeight: 360,
          decoration: const InputDecoration(
            isDense: true,
            contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            border: OutlineInputBorder(),
          ),
          selectedItemBuilder: (context) => _categories
              .map(
                (category) => Text(
                  category['title']?.toString() ?? '',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
                ),
              )
              .toList(),
          items: items,
          onChanged: (value) {
            if (value == null) return;
            final category = _categories.firstWhere(
              (c) => c['code']?.toString() == value,
              orElse: () => const <String, dynamic>{},
            );
            final reasons = category['reasons'] as List<dynamic>? ?? const [];
            final firstReason = reasons.isEmpty
                ? null
                : (reasons.first as Map<String, dynamic>)['code']?.toString();
            setState(() {
              _selectedCategoryCode = value;
              _selectedReasonCode = firstReason;
            });
          },
        ),
      ],
    );
  }

  Widget _buildReasonSelector(bool isRu, Locale locale) {
    final reasons = _selectedCategoryReasons;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          isRu ? 'Причина' : 'Reason',
          style: TextStyle(
            fontFamily: AppTypography.headerFont(locale),
            fontSize: 18,
          ),
        ),
        const SizedBox(height: 6),
        ...reasons.map((reason) {
          final code = reason['code']?.toString() ?? '';
          final title = reason['title']?.toString() ?? '';
          final description = reason['description']?.toString();
          return RadioListTile<String>(
            dense: true,
            contentPadding: EdgeInsets.zero,
            visualDensity: const VisualDensity(vertical: -2),
            isThreeLine: description != null && description.isNotEmpty,
            value: code,
            groupValue: _selectedReasonCode,
            onChanged: (value) => setState(() => _selectedReasonCode = value),
            activeColor: AppColors.accent,
            title: Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontFamily: AppTypography.bodyFont(locale)),
            ),
            subtitle: description == null || description.isEmpty
                ? null
                : Text(
                    description,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontFamily: AppTypography.bodyFont(locale),
                      fontSize: 12,
                    ),
                  ),
          );
        }),
      ],
    );
  }
}
