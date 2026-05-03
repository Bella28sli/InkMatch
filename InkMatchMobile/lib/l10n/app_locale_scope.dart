import 'package:flutter/widgets.dart';

class AppLocaleScope extends InheritedWidget {
  const AppLocaleScope({
    super.key,
    required this.locale,
    required this.toggle,
    required this.isDarkTheme,
    required this.toggleTheme,
    required super.child,
  });

  final Locale locale;
  final VoidCallback toggle;
  final bool isDarkTheme;
  final VoidCallback toggleTheme;

  static AppLocaleScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppLocaleScope>();
    assert(scope != null, 'AppLocaleScope not found');
    return scope!;
  }

  @override
  bool updateShouldNotify(covariant AppLocaleScope oldWidget) {
    return oldWidget.locale != locale || oldWidget.isDarkTheme != isDarkTheme;
  }
}
