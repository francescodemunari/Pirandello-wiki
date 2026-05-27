import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color bgDark = Color(0xFF05070A);
  static const Color surfaceDark = Color(0xFF0A0C10);
  static const Color amberAccent = Color(0xFFB8926B);
  static const Color silverCyan = Color(0xFF8190B2);
  static const Color textLight = Color(0xFFE1E2E8);
  static const Color textGrey = Color(0xFF8E9099);
  static const Color emeraldAccent = Color(0xFF6BB8B0);

  static ThemeData darkTheme = ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: bgDark,
    primaryColor: silverCyan,
    colorScheme: const ColorScheme.dark(
      primary: silverCyan,
      surface: surfaceDark,
      onSurface: textLight,
    ),
    textTheme: GoogleFonts.interTextTheme().apply(
      bodyColor: textLight,
      displayColor: textLight,
    ).copyWith(
      headlineLarge: GoogleFonts.playfairDisplay(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        color: textLight,
      ),
      titleLarge: GoogleFonts.playfairDisplay(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: textLight,
      ),
      bodyLarge: GoogleFonts.inter(
        fontSize: 15,
        color: textLight,
        height: 1.5,
      ),
    ),
  );
}
