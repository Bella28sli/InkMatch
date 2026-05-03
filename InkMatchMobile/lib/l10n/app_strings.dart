import 'package:flutter/widgets.dart';

import 'app_locale_scope.dart';

class AppStrings {
  static bool _isRu(BuildContext context) {
    return AppLocaleScope.of(context).locale.languageCode == 'ru';
  }

  static String title(BuildContext context) => 'InkMatch';
  static String signIn(BuildContext context) =>
      _isRu(context) ? 'Вход' : 'Sign In';
  static String signUp(BuildContext context) => _isRu(context)
      ? 'Регистрация'
      : 'Sign Up';
  static String verify(BuildContext context) => _isRu(context)
      ? 'Подтверждение'
      : 'Verify';
  static String emailOrPhone(BuildContext context) => _isRu(context)
      ? 'Email или телефон'
      : 'Email / Phone';
  static String email(BuildContext context) => 'Email';
  static String phone(BuildContext context) =>
      _isRu(context) ? 'Телефон' : 'Phone';
  static String password(BuildContext context) =>
      _isRu(context) ? 'Пароль' : 'Password';
  static String repeatPassword(BuildContext context) => _isRu(context)
      ? 'Повтор пароля'
      : 'Repeat password';
  static String help(BuildContext context) =>
      _isRu(context) ? 'Помощь' : 'Help';
  static String back(BuildContext context) =>
      _isRu(context) ? 'Назад' : 'Back';
  static String next(BuildContext context) =>
      _isRu(context) ? 'Далее' : 'Next';
  static String finish(BuildContext context) =>
      _isRu(context) ? 'Готово' : 'Finish';
  static String roleClient(BuildContext context) =>
      _isRu(context) ? 'Клиент' : 'Client';
  static String roleMaster(BuildContext context) =>
      _isRu(context) ? 'Мастер' : 'Master';
  static String nickname(BuildContext context) => _isRu(context)
      ? 'Никнейм'
      : 'Nickname';
  static String avatar(BuildContext context) =>
      _isRu(context) ? 'Аватар' : 'Avatar';
  static String experience(BuildContext context) => _isRu(context)
      ? 'Опыт (лет)'
      : 'Experience (years)';
  static String city(BuildContext context) =>
      _isRu(context) ? 'Город' : 'City';
  static String chooseStyles(BuildContext context) => _isRu(context)
      ? 'Выберите 3 фото, которые отражают ваш вкус'
      : 'Pick 3 photos that reflect your taste';
  static String chooseTags(BuildContext context) => _isRu(context)
      ? 'Выберите 3 фото, которые отражают ваш вкус'
      : 'Pick 3 photos that reflect your taste';
  static String code(BuildContext context) =>
      _isRu(context) ? 'Код' : 'Code';
  static String requestCode(BuildContext context) => _isRu(context)
      ? 'Запросить код'
      : 'Request code';
  static String confirm(BuildContext context) => _isRu(context)
      ? 'Подтвердить'
      : 'Confirm';
  static String regByEmail(BuildContext context) =>
      _isRu(context) ? 'По email' : 'By email';
  static String regByPhone(BuildContext context) => _isRu(context)
      ? 'По телефону'
      : 'By phone';
  static String forgotPassword(BuildContext context) => _isRu(context)
      ? 'Забыли пароль?'
      : 'Forgot password?';
  static String resetPassword(BuildContext context) => _isRu(context)
      ? 'Сброс пароля'
      : 'Reset password';
  static String sendResetEmail(BuildContext context) => _isRu(context)
      ? 'Отправить письмо'
      : 'Send reset email';
  static String resetCode(BuildContext context) => _isRu(context)
      ? 'Код из письма (oobCode или ссылка)'
      : 'Code from email (oobCode or link)';
  static String newPassword(BuildContext context) => _isRu(context)
      ? 'Новый пароль'
      : 'New password';
  static String passwordResetSent(BuildContext context) => _isRu(context)
      ? 'Письмо для сброса отправлено.'
      : 'Password reset email sent.';
  static String passwordResetDone(BuildContext context) => _isRu(context)
      ? 'Пароль обновлен. Войдите заново.'
      : 'Password has been reset. Please sign in.';

  static String errNickname(BuildContext context) => _isRu(context)
      ? 'Введите никнейм (2-64 символа)'
      : 'Enter nickname (2-64 chars)';
  static String errLogin(BuildContext context) => _isRu(context)
      ? 'Введите email или телефон'
      : 'Enter email or phone';
  static String errPassword(BuildContext context) => _isRu(context)
      ? 'Введите пароль'
      : 'Enter password';
  static String errPasswordShort(BuildContext context) => _isRu(context)
      ? 'Минимум 8 символов'
      : 'Minimum 8 characters';

  static String errPasswordCase(BuildContext context) => _isRu(context)
      ? 'Пароль должен содержать строчные и заглавные буквы'
      : 'Password must include lowercase and uppercase letters';
  static String errPasswordMismatch(BuildContext context) => _isRu(context)
      ? 'Пароли не совпадают'
      : 'Passwords do not match';
  static String errNeedLogin(BuildContext context) => _isRu(context)
      ? 'Нужен email или телефон'
      : 'Email or phone required';
  static String errExperience(BuildContext context) => _isRu(context)
      ? 'Введите корректный опыт (1-60)'
      : 'Enter valid experience (1-60)';
  static String errPick3Styles(BuildContext context) => _isRu(context)
      ? 'Выберите 3 стиля'
      : 'Pick 3 styles';
  static String errPick3Tags(BuildContext context) => _isRu(context)
      ? 'Выберите 3 тега'
      : 'Pick 3 tags';
  static String errRepeatPassword(BuildContext context) => _isRu(context)
      ? 'Повторите пароль'
      : 'Repeat password';
  static String errInvalidCredentials(BuildContext context) => _isRu(context)
      ? 'Неверный логин или пароль'
      : 'Invalid login or password';
  static String errRegisterFailed(BuildContext context) => _isRu(context)
      ? 'Ошибка регистрации'
      : 'Registration failed';
  static String errCode(BuildContext context) => _isRu(context)
      ? 'Введите код'
      : 'Enter code';
  static String errEmailInvalid(BuildContext context) => _isRu(context)
      ? 'Некорректный email'
      : 'Invalid email';
  static String errPhoneInvalid(BuildContext context) => _isRu(context)
      ? 'Некорректный телефон'
      : 'Invalid phone number';
  static String errResetCode(BuildContext context) => _isRu(context)
      ? 'Введите код из письма'
      : 'Enter reset code';

  static String errValidation(BuildContext context) => _isRu(context)
      ? 'Проверьте корректность полей'
      : 'Please check input fields';
  static String errNetwork(BuildContext context) => _isRu(context)
      ? 'Нет соединения с сервером'
      : 'Cannot reach server';
  static String errTimeout(BuildContext context) => _isRu(context)
      ? 'Сервер отвечает слишком долго'
      : 'Server response timeout';
  static String errServer(BuildContext context) => _isRu(context)
      ? 'Ошибка сервера. Попробуйте позже'
      : 'Server error. Try again later';
  static String errForbidden(BuildContext context) => _isRu(context)
      ? 'Недостаточно прав для действия'
      : 'You do not have permission';
  static String errNotFound(BuildContext context) => _isRu(context)
      ? 'Данные не найдены'
      : 'Data not found';
  static String errConflict(BuildContext context) => _isRu(context)
      ? 'Такие данные уже существуют'
      : 'Data already exists';
  static String errUnknown(BuildContext context) => _isRu(context)
      ? 'Неизвестная ошибка'
      : 'Unknown error';

  static String codeSent(BuildContext context) => _isRu(context)
      ? 'Код отправлен (проверьте консоль API).'
      : 'Code sent (check API console).';
  static String verified(BuildContext context) => _isRu(context)
      ? 'Аккаунт подтвержден. Можно войти.'
      : 'Account verified. You can sign in.';
}
