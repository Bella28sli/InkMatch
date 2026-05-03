import 'dart:async';

import 'package:flutter/material.dart';

import '../services/app_session.dart';
import '../theme/app_colors.dart';
import 'login_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  static const route = '/';

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Timer(const Duration(seconds: 2), () {
      if (!mounted) return;
      final target = AppSession.instance.accessToken?.isNotEmpty == true
          ? '/demo-feed'
          : LoginScreen.route;
      Navigator.pushReplacementNamed(context, target);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/img/bg_light.png', fit: BoxFit.cover),
          Container(color: AppColors.ink.withOpacity(0.08)),
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 280,
                height: 280,
                decoration: const BoxDecoration(
                  color: AppColors.ink,
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: SizedBox(
                    width: 220,
                    height: 220,
                    child: Image.asset('assets/img/logo.png', fit: BoxFit.contain),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}



