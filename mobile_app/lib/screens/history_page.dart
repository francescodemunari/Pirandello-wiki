import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../services/socket_service.dart';
import '../theme/app_theme.dart';

class HistoryPage extends StatefulWidget {
  final VoidCallback onOpenChat;

  const HistoryPage({super.key, required this.onOpenChat});

  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  final _searchCtrl = TextEditingController();
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SocketService>().fetchSessions();
    });
    _searchCtrl.addListener(_onSearchChanged);
  }

  void _onSearchChanged() {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 280), () {
      if (!mounted) return;
      context.read<SocketService>().fetchSessions(query: _searchCtrl.text);
    });
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SocketService>(
      builder: (context, svc, _) {
        return Scaffold(
          backgroundColor: AppTheme.bgDark,
          body: SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 16, 8),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.chevron_right, color: Colors.white54),
                        onPressed: widget.onOpenChat,
                        tooltip: 'Chat',
                      ),
                      const Icon(Icons.history, color: Colors.white54),
                      const SizedBox(width: 8),
                      Text(
                        'Cronologia',
                        style: GoogleFonts.playfairDisplay(
                          fontSize: 22,
                          color: Colors.white,
                        ),
                      ),
                      const Spacer(),
                      TextButton.icon(
                        onPressed: () {
                          svc.newChat();
                          widget.onOpenChat();
                        },
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Nuova'),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: TextField(
                    controller: _searchCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    decoration: InputDecoration(
                      hintText: 'Cerca per titolo o testo...',
                      hintStyle: TextStyle(
                        color: Colors.white.withValues(alpha: 0.2),
                        fontSize: 13,
                      ),
                      prefixIcon: Icon(
                        Icons.search,
                        color: Colors.white.withValues(alpha: 0.3),
                        size: 20,
                      ),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    svc.mode == 'pirandello' ? 'Modalità Pirandello' : 'Modalità Wiki',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Expanded(
                  child: svc.sessions.isEmpty
                      ? Center(
                          child: Text(
                            _searchCtrl.text.trim().isNotEmpty
                                ? 'Nessun risultato'
                                : 'Nessuna conversazione',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.3),
                            ),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          itemCount: svc.sessions.length,
                          itemBuilder: (_, i) {
                            final s = svc.sessions[i];
                            final active = s.id == svc.sessionId;
                            return ListTile(
                              title: Text(
                                s.title,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: active
                                      ? Colors.amber.shade100
                                      : Colors.white,
                                  fontWeight: active
                                      ? FontWeight.w600
                                      : FontWeight.normal,
                                  fontSize: 14,
                                ),
                              ),
                              subtitle: Text(
                                s.createdAt,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.white.withValues(alpha: 0.35),
                                ),
                              ),
                              trailing: IconButton(
                                icon: Icon(
                                  Icons.delete_outline,
                                  color: Colors.red.shade300
                                      .withValues(alpha: 0.7),
                                  size: 20,
                                ),
                                onPressed: () => svc.deleteSession(s.id),
                              ),
                              onTap: () async {
                                await svc.loadSession(s.id);
                                widget.onOpenChat();
                              },
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
