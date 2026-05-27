import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/message.dart';
import '../theme/app_theme.dart';
import 'glass_container.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool useMarkdown;
  final bool showTtsButton;
  final VoidCallback? onPlayTts;

  const MessageBubble({
    super.key,
    required this.message,
    this.useMarkdown = false,
    this.showTtsButton = false,
    this.onPlayTts,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == MessageSender.user;
    final isSys = message.sender == MessageSender.system;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          Flexible(
            child: GlassContainer(
              borderRadius: 16,
              opacity: isUser ? 0.08 : 0.03,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                constraints: BoxConstraints(
                  maxWidth: MediaQuery.of(context).size.width * 0.78,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (message.isPreparing)
                      Text(
                        'Sta preparando la risposta…',
                        style: GoogleFonts.playfairDisplay(
                          color: Colors.white.withValues(alpha: 0.45),
                          fontSize: 14,
                          fontStyle: FontStyle.italic,
                        ),
                      )
                    else if (useMarkdown &&
                        !isUser &&
                        !isSys &&
                        message.text.isNotEmpty)
                      MarkdownBody(
                        data: message.text,
                        selectable: true,
                        styleSheet: MarkdownStyleSheet(
                          p: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            height: 1.45,
                          ),
                          h1: TextStyle(
                            color: Colors.teal.shade100,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                          h2: TextStyle(
                            color: Colors.teal.shade100,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                          code: TextStyle(
                            color: Colors.teal.shade200,
                            backgroundColor: Colors.white.withValues(alpha: 0.06),
                            fontFamily: 'monospace',
                            fontSize: 12,
                          ),
                          codeblockDecoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.04),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          blockquote: TextStyle(
                            color: Colors.white70,
                            fontStyle: FontStyle.italic,
                          ),
                          listBullet: const TextStyle(color: Colors.white70),
                          a: TextStyle(
                            color: AppTheme.emeraldAccent,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      )
                    else
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Flexible(
                            child: Text(
                              message.text,
                              style: isSys
                                  ? const TextStyle(
                                      color: Colors.white54,
                                      fontSize: 12,
                                      fontFamily: 'monospace',
                                    )
                                  : isUser
                                      ? const TextStyle(
                                          color: Colors.white,
                                          fontSize: 14,
                                        )
                                      : GoogleFonts.playfairDisplay(
                                          color: Colors.white,
                                          fontSize: 14,
                                          height: 1.4,
                                        ),
                            ),
                          ),
                          if (message.isStreaming)
                            const Padding(
                              padding: EdgeInsets.only(left: 4),
                              child: SizedBox(
                                width: 12,
                                height: 12,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white38,
                                ),
                              ),
                            ),
                        ],
                      ),
                    if (showTtsButton &&
                        !isUser &&
                        !isSys &&
                        message.text.isNotEmpty &&
                        !message.isStreaming)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: InkWell(
                          onTap: onPlayTts,
                          borderRadius: BorderRadius.circular(8),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 2,
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Icons.volume_up,
                                  size: 16,
                                  color: Colors.amber.shade200
                                      .withValues(alpha: 0.7),
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  'Ascolta',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.amber.shade200
                                        .withValues(alpha: 0.6),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
