import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_typography.dart';

ThemeData buildTheme({required bool darkMode}) {
  final locale = const Locale('ru');

  if (darkMode) {
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Comfortaa',
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF151515),
      colorScheme: const ColorScheme.dark(
        primary: AppColors.accent,
        secondary: AppColors.accent,
        surface: Color(0xFF1F1F1F),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF151515),
        foregroundColor: Color(0xFFF1ECE2),
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        color: const Color(0xFF1F1F1F),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Color(0xFF2B2B2B)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF1E1E1E),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF2D2D2D)),
        ),
      ),
      textTheme: TextTheme(
        bodyMedium: TextStyle(
          color: const Color(0xFFF1ECE2),
          fontFamily: AppTypography.bodyFont(locale),
        ),
      ),
    );
  }

  return ThemeData(
    useMaterial3: true,
    fontFamily: 'Comfortaa',
    brightness: Brightness.light,
    scaffoldBackgroundColor: AppColors.background,
    colorScheme: const ColorScheme.light(
      primary: AppColors.accent,
      secondary: AppColors.accent,
      surface: AppColors.surface,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.background,
      foregroundColor: AppColors.ink,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.accent),
      ),
    ),
    textTheme: TextTheme(
      bodyMedium: TextStyle(
        color: AppColors.ink,
        fontFamily: AppTypography.bodyFont(locale),
      ),
      bodySmall: TextStyle(
        color: AppColors.inkSoft,
        fontFamily: AppTypography.bodyFont(locale),
      ),
    ),
  );
}
