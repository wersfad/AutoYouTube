#!/usr/bin/env python3
from pathlib import Path
import tempfile,subprocess,sys,shutil
here=Path(__file__).resolve().parents[1]

def logic():
 javac=shutil.which('javac');java=shutil.which('java')
 if not java:
  raise RuntimeError('Java runtime required for logic tests')
 compiler=[javac] if javac else [java,'com.sun.tools.javac.Main']
 with tempfile.TemporaryDirectory() as d:
  p=Path(d);src=here/'native/android/com/wersfad/autoyoutube/ClipLogic.java'
  test=p/'LogicTest.java';test.write_text('''import java.util.*;import com.wersfad.autoyoutube.ClipLogic;
public class LogicTest {public static void main(String[] a){
 if(ClipLogic.allowedHost("youtube.com.evil.test"))throw new Error("host bypass");
 if(!ClipLogic.allowedHost("www.twitch.tv"))throw new Error("Twitch host");
 if(ClipLogic.overlaps(0,30,30,60))throw new Error("adjacent ranges");
 if(!ClipLogic.overlaps(0,30,29,60))throw new Error("overlap");
 float[] quiet=new float[120*16000];if(!ClipLogic.select(new ArrayList<>(),quiet,16000,120,30,false).isEmpty())throw new Error("invented silent highlight");
 List<ClipLogic.Phrase> speech=Arrays.asList(new ClipLogic.Phrase(10,20,"Смотри, невероятно, победа!"),new ClipLogic.Phrase(20,25,"Это было хорошо"));
 if(ClipLogic.select(speech,quiet,16000,120,30,false).isEmpty())throw new Error("missed reaction");
 var moments=ClipLogic.select(speech,quiet,16000,120,30,false);for(int i=0;i<moments.size();i++)for(int j=i+1;j<moments.size();j++)if(ClipLogic.overlaps(moments.get(i).start,moments.get(i).end,moments.get(j).start,moments.get(j).end))throw new Error("duplicate highlights");
 System.out.println("PASS: host validation, overlaps, silence, reaction selection, deduplication");}}
''')
  subprocess.run(compiler+['-d',str(p),str(src),str(test)],check=True);subprocess.run([java,'-cp',str(p),'LogicTest'],check=True)
if '--logic-only' not in sys.argv:
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)
  for f in ['assets/AutoYouTube.html','lib/native.dart','pubspec.yaml','android/app/build.gradle.kts','android/app/src/main/kotlin/com/wersfad/autoyoutube/MainActivity.kt','android/app/src/main/AndroidManifest.xml']:(p/f).parent.mkdir(parents=True,exist_ok=True)
  (p/'assets/AutoYouTube.html').write_text('''<html><head></head><body><script>function x(){if(!S.channel)S.view='onb';const map={onb:vOnb};const t=[['studio','🎛️','Студия'],];if(S.view==='ideas')bindSwipe()}</script></body></html>''')
  (p/'lib/native.dart').write_text('class Native { Future<dynamic> call(String m, Map<String, dynamic> a) async { return true; } }')
  (p/'pubspec.yaml').write_text('flutter:\n  assets:\n    - assets/AutoYouTube.html\n')
  (p/'android/app/build.gradle.kts').write_text('android {}\n')
  (p/'android/app/src/main/kotlin/com/wersfad/autoyoutube/MainActivity.kt').write_text('package com.wersfad.autoyoutube\nimport io.flutter.embedding.android.FlutterActivity\nclass MainActivity: FlutterActivity()\n')
  (p/'android/app/src/main/AndroidManifest.xml').write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="Test"/></manifest>')
  shutil.copytree(here/'native',p/'native')
  for i in range(2):subprocess.run([sys.executable,str(here/'tools/install_clips.py'),str(p)],check=True)
  h=(p/'assets/AutoYouTube.html').read_text();assert h.count('clips:vClips')==1 and h.count('src="clips.js"')==1
  activity=(p/'android/app/src/main/kotlin/com/wersfad/autoyoutube/MainActivity.kt').read_text();assert activity.count('ClipsBridge.attach')==1
  native=(p/'lib/native.dart').read_text();assert native.count("m.startsWith('clips.')")==1
  assert (p/'android/app/build.gradle.kts').read_text().count('AYT_CLIPS_NATIVE')==1
  assert 'extractNativeLibs="true"' in (p/'android/app/src/main/AndroidManifest.xml').read_text()
  import re
  script=re.search(r'<script>(.*?)</script>',h,re.S).group(1)
  subprocess.run(['node','--check'],input=script,text=True,check=True)
  print('PASS: integration is idempotent, JS insert parses, existing files preserved')
logic()
