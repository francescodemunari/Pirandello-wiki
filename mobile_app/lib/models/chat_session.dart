class ChatSession {
  final String id;
  final String title;
  final String createdAt;
  final String mode;

  ChatSession({
    required this.id,
    required this.title,
    required this.createdAt,
    this.mode = 'pirandello',
  });

  factory ChatSession.fromJson(Map<String, dynamic> json) {
    return ChatSession(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? 'Nuova Conversazione',
      createdAt: json['created_at'] as String? ?? '',
      mode: json['mode'] as String? ?? 'pirandello',
    );
  }
}
