class MemoryFact {
  final String category;
  final String key;
  final String value;

  MemoryFact({
    required this.category,
    required this.key,
    required this.value,
  });

  factory MemoryFact.fromJson(Map<String, dynamic> json) {
    return MemoryFact(
      category: json['category'] as String? ?? '',
      key: json['key'] as String? ?? '',
      value: json['value'] as String? ?? '',
    );
  }
}
