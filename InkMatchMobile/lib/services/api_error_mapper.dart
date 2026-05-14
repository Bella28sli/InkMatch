import 'dart:convert';

import 'package:flutter/widgets.dart';

import '../l10n/app_strings.dart';

class ApiErrorMapper {
  static String mapHttpError(
    BuildContext context,
    int statusCode,
    String body, {
    String? fallback,
  }) {
    dynamic payload;
    final lowered = body.toLowerCase();
    if (body.trim().isNotEmpty) {
      try {
        payload = jsonDecode(body);
      } catch (_) {
        payload = body;
      }
    }

    final details = _extractDetail(payload);
    if (details.isNotEmpty) {
      return details;
    }

    switch (statusCode) {
      case 400:
      case 422:
        return fallback ?? AppStrings.errValidation(context);
      case 401:
        return AppStrings.errInvalidCredentials(context);
      case 403:
        if (lowered.contains('email is not verified')) {
          return 'Подтвердите email, прежде чем входить';
        }
        return AppStrings.errForbidden(context);
      case 404:
        return AppStrings.errNotFound(context);
      case 409:
        return AppStrings.errConflict(context);
      default:
        if (statusCode >= 500) {
          return AppStrings.errServer(context);
        }
        return fallback ?? AppStrings.errUnknown(context);
    }
  }

  static String mapException(BuildContext context, Object error) {
    final raw = error.toString().toLowerCase();
    if (raw.contains('timed out') || raw.contains('timeout')) {
      return AppStrings.errTimeout(context);
    }
    if (raw.contains('socketexception') || raw.contains('failed host lookup')) {
      return AppStrings.errNetwork(context);
    }
    return AppStrings.errUnknown(context);
  }

  static String _extractDetail(dynamic payload) {
    if (payload is Map<String, dynamic>) {
      final detail = payload['detail'];
      if (detail is String && detail.trim().isNotEmpty) {
        return _normalizeDetail(detail);
      }
      if (detail is List) {
        final messages = <String>[];
        for (final item in detail) {
          final msg = _extractValidationItem(item);
          if (msg.isNotEmpty) {
            messages.add(msg);
          }
        }
        if (messages.isNotEmpty) {
          return messages.join('\n');
        }
      }
    }
    if (payload is String && payload.trim().isNotEmpty) {
      return _normalizeDetail(payload);
    }
    return '';
  }

  static String _extractValidationItem(dynamic item) {
    if (item is! Map) return '';

    final msg = item['msg']?.toString().trim() ?? '';
    final locRaw = item['loc'];
    var field = '';
    if (locRaw is List && locRaw.isNotEmpty) {
      field = locRaw.last.toString();
    }

    if (field.isEmpty && msg.isNotEmpty) {
      return _normalizeDetail(msg);
    }

    final fieldTitle = _fieldName(field);
    final normMsg = _normalizeValidationMessage(msg);
    if (fieldTitle.isEmpty) return normMsg;
    return '$fieldTitle: $normMsg';
  }

  static String _fieldName(String raw) {
    switch (raw) {
      case 'email':
      case 'profile.email':
        return 'Email';
      case 'phone':
      case 'profile.phone':
        return 'Телефон';
      case 'password':
        return 'Пароль';
      case 'nickname':
      case 'profile.nickname':
        return 'Никнейм';
      case 'preferred_style_ids':
        return 'Стили';
      case 'preferred_tag_ids':
        return 'Теги';
      case 'role':
        return 'Роль';
      default:
        return raw;
    }
  }

  static String _normalizeDetail(String value) {
    final lowered = value.toLowerCase();
    if (lowered.contains('invalid credentials')) {
      return 'Неверный логин или пароль';
    }
    if (lowered.contains('email or phone already')) {
      return 'Email или телефон уже зарегистрирован';
    }
    if (lowered.contains('invalid registration data')) {
      return 'Некорректные данные регистрации';
    }
    if (lowered.contains('field required')) {
      return 'Не заполнено обязательное поле';
    }
    if (lowered.contains('json decode')) {
      return 'Ошибка формата данных';
    }
    if (lowered.contains('value error')) {
      return 'Некорректное значение';
    }
    if (lowered.contains(
      'password must include lower and upper case letters',
    )) {
      return 'Пароль должен содержать строчные и заглавные буквы';
    }
    return value;
  }

  static String _normalizeValidationMessage(String value) {
    final lowered = value.toLowerCase();
    if (lowered.contains('field required')) {
      return 'обязательное поле';
    }
    if (lowered.contains('valid email')) {
      return 'некорректный email';
    }
    if (lowered.contains('should have at least')) {
      return 'слишком короткое значение';
    }
    if (lowered.contains('should have at most')) {
      return 'слишком длинное значение';
    }
    if (lowered.contains('input should be')) {
      return 'некорректный формат';
    }
    if (lowered.contains(
      'password must include lower and upper case letters',
    )) {
      return 'пароль должен содержать строчные и заглавные буквы';
    }
    return value;
  }
}
