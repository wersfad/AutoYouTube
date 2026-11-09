import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

/// Native methods called from the web app: nat(method, args).
class Native {
  final Map<String, IOSink> _sinks = {};
  final Map<String, String> _paths = {};

  Future<dynamic> call(String m, Map<String, dynamic> a) async {
    switch (m) {
      case 'http':
        return _http(a);
      case 'open':
        await launchUrl(Uri.parse(a['url'].toString()), mode: LaunchMode.externalApplication);
        return true;
      case 'fileBegin':
        return _fileBegin(a['name'].toString());
      case 'fileChunk':
        final s = _sinks[a['name'].toString()];
        if (s == null) throw Exception('file not started');
        s.add(base64Decode(a['b64'].toString()));
        return true;
      case 'fileEnd':
        final name = a['name'].toString();
        final s2 = _sinks.remove(name);
        if (s2 == null) throw Exception('file not started');
        await s2.flush();
        await s2.close();
        return _paths.remove(name);
      case 'share':
        await Share.shareXFiles([XFile(a['path'].toString(), mimeType: a['mime']?.toString())]);
        return true;
      case 'ytUpload':
        return _ytUpload(a);
      case 'ytThumb':
        final r = await http.post(
          Uri.parse('https://www.googleapis.com/upload/youtube/v3/thumbnails/set?uploadType=media&videoId=${a['videoId']}'),
          headers: {
            'Authorization': 'Bearer ${a['token']}',
            'Content-Type': (a['mime'] ?? 'image/jpeg').toString(),
          },
          body: base64Decode(a['b64'].toString()),
        );
        return {'status': r.statusCode, 'body': r.body};
    }
    throw Exception('unknown method $m');
  }

  Future<String> _fileBegin(String name) async {
    final dir = await getApplicationDocumentsDirectory();
    final vd = Directory('${dir.path}/videos');
    if (!await vd.exists()) await vd.create(recursive: true);
    final path = '${vd.path}/$name';
    final old = _sinks.remove(name);
    if (old != null) await old.close();
    _sinks[name] = File(path).openWrite();
    _paths[name] = path;
    return path;
  }

  Future<Map<String, dynamic>> _http(Map<String, dynamic> a) async {
    final req = http.Request((a['method'] ?? 'GET').toString(), Uri.parse(a['url'].toString()));
    final h = a['headers'];
    if (h is Map) {
      h.forEach((k, v) => req.headers[k.toString()] = v.toString());
    }
    final b = a['body'];
    if (b != null) req.bodyBytes = utf8.encode(b.toString());
    final client = http.Client();
    try {
      final r = await client.send(req).timeout(const Duration(seconds: 60));
      final body = await r.stream.bytesToString();
      return {'status': r.statusCode, 'body': body};
    } finally {
      client.close();
    }
  }

  Future<Map<String, dynamic>> _ytUpload(Map<String, dynamic> a) async {
    final f = File(a['path'].toString());
    final len = await f.length();
    final mime = (a['mime'] ?? 'video/mp4').toString();
    final init = await http.post(
      Uri.parse('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'),
      headers: {
        'Authorization': 'Bearer ${a['token']}',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Length': '$len',
        'X-Upload-Content-Type': mime,
      },
      body: jsonEncode(a['meta']),
    );
    final loc = init.headers['location'];
    if (init.statusCode != 200 || loc == null) {
      return {'status': init.statusCode, 'body': init.body};
    }
    final req = http.StreamedRequest('PUT', Uri.parse(loc));
    req.headers['Content-Type'] = mime;
    req.contentLength = len;
    final client = http.Client();
    try {
      final sending = client.send(req);
      await f.openRead().forEach(req.sink.add);
      await req.sink.close();
      final r = await sending;
      final body = await r.stream.bytesToString();
      return {'status': r.statusCode, 'body': body};
    } finally {
      client.close();
    }
  }
}
