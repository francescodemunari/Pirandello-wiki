enum MessageSender { user, assistant, system }

class ChatMessage {
  final String id;
  final String text;
  final MessageSender sender;
  final DateTime timestamp;
  final bool isStreaming;
  final bool isPreparing;
  final String? audioUrl;

  ChatMessage({
    required this.id,
    required this.text,
    required this.sender,
    required this.timestamp,
    this.isStreaming = false,
    this.isPreparing = false,
    this.audioUrl,
  });

  ChatMessage copyWith({
    String? text,
    bool? isStreaming,
    bool? isPreparing,
    String? audioUrl,
  }) {
    return ChatMessage(
      id: id,
      text: text ?? this.text,
      sender: sender,
      timestamp: timestamp,
      isStreaming: isStreaming ?? this.isStreaming,
      isPreparing: isPreparing ?? this.isPreparing,
      audioUrl: audioUrl ?? this.audioUrl,
    );
  }
}
