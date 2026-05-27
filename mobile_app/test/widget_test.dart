import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:pirandello_mobile/main.dart';
import 'package:pirandello_mobile/services/socket_service.dart';

void main() {
  testWidgets('App loads chat home', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => SocketService(),
        child: const PirandelloApp(),
      ),
    );
    await tester.pump();
    expect(find.text('Pirandello'), findsOneWidget);
  });
}
