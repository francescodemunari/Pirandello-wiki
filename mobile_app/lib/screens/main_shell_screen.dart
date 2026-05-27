import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/socket_service.dart';
import 'chat_screen.dart';
import 'history_page.dart';
import 'settings_page.dart';

/// Shell con tre pagine: Cronologia ← Chat → Impostazioni (swipe orizzontale).
class MainShellScreen extends StatefulWidget {
  const MainShellScreen({super.key});

  static const int historyIndex = 0;
  static const int chatIndex = 1;
  static const int settingsIndex = 2;

  @override
  State<MainShellScreen> createState() => _MainShellScreenState();
}

class _MainShellScreenState extends State<MainShellScreen> {
  late final PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: MainShellScreen.chatIndex);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goTo(int index) {
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    return PageView(
      controller: _pageController,
      physics: const BouncingScrollPhysics(),
      children: [
        HistoryPage(onOpenChat: () => _goTo(MainShellScreen.chatIndex)),
        ChatScreen(
          onOpenHistory: () {
            context.read<SocketService>().fetchSessions();
            _goTo(MainShellScreen.historyIndex);
          },
          onOpenSettings: () {
            context.read<SocketService>().fetchMemories();
            _goTo(MainShellScreen.settingsIndex);
          },
        ),
        SettingsPage(onOpenChat: () => _goTo(MainShellScreen.chatIndex)),
      ],
    );
  }
}
