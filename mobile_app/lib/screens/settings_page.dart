import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../config/app_config.dart';
import '../services/socket_service.dart';
import '../theme/app_theme.dart';

class SettingsPage extends StatefulWidget {
  final VoidCallback onOpenChat;

  const SettingsPage({super.key, required this.onOpenChat});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _urlCtrl;
  final Map<String, TextEditingController> _providerApiUrlCtrls = {};
  final Map<String, TextEditingController> _providerModelCtrls = {};
  final Map<String, TextEditingController> _providerApiKeyCtrls = {};
  String? _expandedProvider;

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final svc = context.read<SocketService>();
      _urlCtrl.text = svc.serverUrl;
      svc.fetchMemories();
      svc.fetchProviders();
    });
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    for (final c in _providerApiUrlCtrls.values) c.dispose();
    for (final c in _providerModelCtrls.values) c.dispose();
    for (final c in _providerApiKeyCtrls.values) c.dispose();
    super.dispose();
  }

  Widget _buildProviderSection(SocketService svc) {
    final providers = svc.providers;
    if (providers.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 20),
        Row(
          children: [
            Icon(Icons.memory, size: 14, color: Colors.amber.shade200.withValues(alpha: 0.7)),
            const SizedBox(width: 6),
            Text(
              'Provider modello',
              style: TextStyle(
                fontSize: 11,
                color: Colors.white.withValues(alpha: 0.5),
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Container(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.03),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
          ),
          child: Column(
            children: providers.entries.map((entry) {
              final name = entry.key;
              final p = entry.value as Map<String, dynamic>;
              final isActive = svc.activeProvider == name;
              final isExpanded = _expandedProvider == name;
              final category = p['category'] as String? ?? 'local';
              final displayName = p['display_name'] as String? ?? name;
              final model = p['model'] as String? ?? '';
              final apiUrl = p['api_url'] as String? ?? '';

              _providerApiUrlCtrls.putIfAbsent(name, () => TextEditingController(text: apiUrl));
              _providerModelCtrls.putIfAbsent(name, () => TextEditingController(text: model));
              final savedKey = p['api_key'] as String? ?? '';
              _providerApiKeyCtrls.putIfAbsent(name, () => TextEditingController(text: savedKey));

              return Column(
                children: [
                  if (entry.key != providers.entries.first)
                    Divider(height: 1, color: Colors.white.withValues(alpha: 0.05)),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    child: Row(
                      children: [
                        Container(
                          width: 32, height: 32,
                          decoration: BoxDecoration(
                            color: isActive
                                ? AppTheme.amberAccent.withValues(alpha: 0.2)
                                : Colors.white.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            category == 'local' ? Icons.computer : Icons.cloud,
                            size: 16,
                            color: isActive ? AppTheme.amberAccent : Colors.white38,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                displayName,
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                                  color: isActive ? Colors.amber.shade100 : Colors.white70,
                                ),
                              ),
                              if (model.isNotEmpty)
                                Text(
                                  model,
                                  style: TextStyle(fontSize: 10, color: Colors.white.withValues(alpha: 0.35)),
                                  maxLines: 1, overflow: TextOverflow.ellipsis,
                                ),
                            ],
                          ),
                        ),
                        GestureDetector(
                          onTap: () => svc.activateProvider(name),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                              color: isActive
                                  ? AppTheme.amberAccent.withValues(alpha: 0.2)
                                  : Colors.white.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: isActive
                                    ? AppTheme.amberAccent.withValues(alpha: 0.3)
                                    : Colors.white.withValues(alpha: 0.1),
                              ),
                            ),
                            child: Text(
                              isActive ? 'Attivo' : 'Attiva',
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.5,
                                color: isActive ? AppTheme.amberAccent : Colors.white38,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        GestureDetector(
                          onTap: () => setState(() => _expandedProvider = isExpanded ? null : name),
                          child: Padding(
                            padding: const EdgeInsets.all(4),
                            child: Icon(
                              isExpanded ? Icons.expand_less : Icons.expand_more,
                              size: 18,
                              color: Colors.white38,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (isExpanded)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          _configField('API URL', _providerApiUrlCtrls[name]!,
                              p['api_url'] as String? ?? 'URL del provider...'),
                          const SizedBox(height: 8),
                          _configField('Modello', _providerModelCtrls[name]!,
                              p['model'] as String? ?? 'Nome modello...'),
                          if (category == 'cloud') ...{
                            const SizedBox(height: 8),
                            _configField('API Key', _providerApiKeyCtrls[name]!,
                                'Inserisci API key...', obscure: true),
                          },
                          const SizedBox(height: 8),
                          OutlinedButton(
                            onPressed: () {
                              svc.updateProviderConfig(name, {
                                'api_url': _providerApiUrlCtrls[name]!.text,
                                'model': _providerModelCtrls[name]!.text,
                                if (category == 'cloud')
                                  'api_key': _providerApiKeyCtrls[name]!.text,
                              });
                            },
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.white54,
                              side: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                              padding: const EdgeInsets.symmetric(vertical: 10),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                            child: const Text('Salva', style: TextStyle(fontSize: 11)),
                          ),
                        ],
                      ),
                    ),
                ],
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _configField(String label, TextEditingController ctrl, String hint,
      {bool obscure = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(fontSize: 9, color: Colors.white.withValues(alpha: 0.35),
              letterSpacing: 0.5),
        ),
        const SizedBox(height: 4),
        TextField(
          controller: ctrl,
          obscureText: obscure,
          style: const TextStyle(color: Colors.white, fontSize: 12),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.15), fontSize: 11),
            filled: true,
            fillColor: Colors.white.withValues(alpha: 0.05),
            contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SocketService>(
      builder: (context, svc, _) {
        return Scaffold(
          backgroundColor: AppTheme.bgDark,
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.chevron_left, color: Colors.white54),
                        onPressed: widget.onOpenChat,
                        tooltip: 'Chat',
                      ),
                      Text(
                        'Impostazioni',
                        style: GoogleFonts.playfairDisplay(fontSize: 22, color: Colors.white),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Server (Tailscale / LAN)',
                    style: TextStyle(fontSize: 12, color: Colors.white.withValues(alpha: 0.5)),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _urlCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: AppConfig.tailscaleHint,
                      hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.2), fontSize: 12),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Sul PC: tailscale ip -4\n'
                    'Inserisci IP: porta (es. 100.x.x.x:8000)',
                    style: TextStyle(fontSize: 10, color: Colors.white.withValues(alpha: 0.35), height: 1.4),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () async {
                            final result = await svc.testConnection(_urlCtrl.text);
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text(result.message), duration: const Duration(seconds: 5)),
                            );
                          },
                          child: const Text('Test connessione'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: FilledButton(
                          onPressed: () async {
                            await svc.updateServerUrl(_urlCtrl.text);
                            final result = await svc.testConnection();
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text(result.message)),
                            );
                          },
                          child: const Text('Applica'),
                        ),
                      ),
                    ],
                  ),

                  // --- Provider section ---
                  _buildProviderSection(svc),

                  const SizedBox(height: 20),
                  SwitchListTile(
                    title: const Text('Autoplay voce', style: TextStyle(color: Colors.white, fontSize: 14)),
                    subtitle: Text(
                      'Giuseppe (it-IT) dopo ogni risposta',
                      style: TextStyle(fontSize: 11, color: Colors.white.withValues(alpha: 0.4)),
                    ),
                    value: svc.autoplay,
                    activeThumbColor: AppTheme.amberAccent,
                    onChanged: svc.setAutoplay,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Memoria utente',
                    style: TextStyle(fontSize: 12, color: Colors.white.withValues(alpha: 0.5)),
                  ),
                  const SizedBox(height: 8),
                  if (svc.memories.isEmpty)
                    Text(
                      'Nessun fatto memorizzato',
                      style: TextStyle(fontSize: 12, color: Colors.white.withValues(alpha: 0.3)),
                    )
                  else
                    ...svc.memories.map(
                      (m) => ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          '${m.category} / ${m.key}',
                          style: const TextStyle(color: Colors.white70, fontSize: 12),
                        ),
                        subtitle: Text(
                          m.value,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 11, color: Colors.white.withValues(alpha: 0.4)),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.close, size: 16),
                          color: Colors.white38,
                          onPressed: () => svc.deleteMemory(m.category, m.key),
                        ),
                      ),
                    ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: () async {
                      final confirm = await showDialog<bool>(
                        context: context,
                        builder: (dCtx) => AlertDialog(
                          backgroundColor: AppTheme.bgDark,
                          title: const Text('Reset completo?'),
                          content: const Text('Elimina tutte le chat e la memoria utente.'),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(dCtx, false),
                              child: const Text('Annulla'),
                            ),
                            TextButton(
                              onPressed: () => Navigator.pop(dCtx, true),
                              child: Text('Reset', style: TextStyle(color: Colors.red.shade300)),
                            ),
                          ],
                        ),
                      );
                      if (confirm == true) {
                        await svc.hardReset();
                        widget.onOpenChat();
                      }
                    },
                    icon: const Icon(Icons.delete_forever, size: 18),
                    label: const Text('Reset (chat + memoria)'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.red.shade300,
                      side: BorderSide(color: Colors.red.shade300.withValues(alpha: 0.4)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
