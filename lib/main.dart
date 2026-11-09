import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

import 'native.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Color(0xFF07070A),
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: Color(0xFF07070A),
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  runApp(const AutoYouTubeApp());
}

class AutoYouTubeApp extends StatelessWidget {
  const AutoYouTubeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AutoYouTube',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF07070A),
        colorScheme: const ColorScheme.dark(primary: Color(0xFFFF2D3D)),
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late final WebViewController _c;
  final Native _native = Native();
  DateTime? _lastBack;

  @override
  void initState() {
    super.initState();
    _c = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF07070A))
      ..addJavaScriptChannel('AYT', onMessageReceived: _onMessage)
      ..setOnJavaScriptAlertDialog((r) async {
        await _dialog(r.message, false);
      })
      ..setOnJavaScriptConfirmDialog((r) async {
        return await _dialog(r.message, true);
      });

    final p = _c.platform;
    if (p is AndroidWebViewController) {
      p.setMediaPlaybackRequiresUserGesture(false);
      p.setOnShowFileSelector(_pickFile);
    }
    _c.loadFlutterAsset('assets/AutoYouTube.html');
  }

  Future<List<String>> _pickFile(FileSelectorParams params) async {
    final types = params.acceptTypes.join(',');
    FileType t = FileType.any;
    if (types.contains('image')) t = FileType.image;
    if (types.contains('video')) t = FileType.video;
    final res = await FilePicker.platform.pickFiles(type: t);
    final path = res?.files.single.path;
    if (path == null) return [];
    return [Uri.file(path).toString()];
  }

  Future<void> _onMessage(JavaScriptMessage m) async {
    try {
      final j = jsonDecode(m.message) as Map<String, dynamic>;
      final type = j['t'];
      final value = (j['v'] ?? '').toString();
      if (type == 'call') {
        _handleCall(j);
        return;
      }
      if (type == 'copy') {
        await Clipboard.setData(ClipboardData(text: value));
      } else if (type == 'file') {
        final dir = await getTemporaryDirectory();
        final name = (j['name'] ?? 'file.txt').toString();
        final f = File('${dir.path}/$name');
        await f.writeAsString(value);
        await Share.shareXFiles([XFile(f.path)], text: name);
      } else if (type == 'open') {
        await Share.share(value);
      }
    } catch (_) {}
  }

  Future<void> _handleCall(Map<String, dynamic> j) async {
    final id = jsonEncode(j['id']);
    try {
      final args = (j['a'] is Map) ? Map<String, dynamic>.from(j['a'] as Map) : <String, dynamic>{};
      final res = await _native.call(j['m'].toString(), args);
      await _c.runJavaScript('aytReply($id, true, ${jsonEncode(res)})');
    } catch (e) {
      await _c.runJavaScript('aytReply($id, false, ${jsonEncode(e.toString())})');
    }
  }

  Future<bool> _dialog(String text, bool ask) async {
    final r = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF16161C),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        content: Text(text, style: const TextStyle(color: Colors.white)),
        actions: [
          if (ask)
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('OK', style: TextStyle(color: Color(0xFFFF2D3D))),
          ),
        ],
      ),
    );
    return r ?? false;
  }

  Future<void> _onBack() async {
    final handled = await _c.runJavaScriptReturningResult('window.aytBack ? aytBack() : false');
    if (handled.toString() == 'true') return;
    final now = DateTime.now();
    if (_lastBack != null && now.difference(_lastBack!) < const Duration(seconds: 2)) {
      SystemNavigator.pop();
      return;
    }
    _lastBack = now;
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Нажмите «Назад» ещё раз, чтобы выйти'),
      duration: Duration(seconds: 2),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _onBack();
      },
      child: Scaffold(
        body: SafeArea(child: WebViewWidget(controller: _c)),
      ),
    );
  }
}
