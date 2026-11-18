#!/usr/bin/env python3
"""Gallery source for Clips: pick a local video and cut it on the phone (no download).
Run AFTER tools/install_clips.py and BEFORE flutter pub get. Idempotent."""
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
MARK='AYT_GALLERY'

def patch(path,pairs,name):
    s=path.read_text(encoding='utf-8')
    if MARK in s:
        print('[gallery] already patched:',name);return
    for old,new in pairs:
        assert old in s, f'[gallery] anchor not found in {name}: {old[:70]!r}'
        s=s.replace(old,new,1)
    path.write_text(s,encoding='utf-8');print('[gallery] patched:',name)

# 1) pubspec: file picker plugin
pub=root/'pubspec.yaml';s=pub.read_text(encoding='utf-8')
if 'file_picker:' not in s:
    assert '\ndependencies:\n' in s,'[gallery] dependencies: not found in pubspec.yaml'
    s=s.replace('\ndependencies:\n','\ndependencies:\n  file_picker: ^8.3.7 # AYT_GALLERY\n',1);pub.write_text(s,encoding='utf-8');print('[gallery] patched: pubspec.yaml')

# 2) Dart bridge: pickVideo -> local file path (or null on cancel)
patch(root/'lib/native.dart',[
 ("import 'dart:async';","import 'dart:async';\nimport 'package:file_picker/file_picker.dart'; // AYT_GALLERY"),
 ("case 'http':","case 'pickVideo':\n        final picked = await FilePicker.platform.pickFiles(type: FileType.video, allowMultiple: false);\n        return picked?.files.single.path;\n      case 'http':"),
],'lib/native.dart')

# 3) Java service: accept {local: path}
svc=root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsService.java'
assert svc.exists(),'[gallery] ClipsService.java not installed: run install_clips.py first'
LOCAL_METHOD=r"""
 // AYT_GALLERY: local video from the gallery, cut in windows like a published video
 private void localFile(File src)throws Exception{
  if(!src.isFile())throw new IOException("Файл из галереи не найден");
  double duration=seconds(src);if(duration<12)throw new IOException("Видео слишком короткое");
  double cursor=0;synchronized(LOCK){state.put("availableSeconds",duration).put("scannedSeconds",0);persist();}
  while(!stopping&&created()<maxClips&&duration-cursor>=12){
   check();double start=Math.max(0,cursor-OVERLAP),end=Math.min(duration,Math.max(cursor,start)+WINDOW);
   phase("history","Видео из галереи: фрагмент "+(int)start+"–"+(int)end+" из "+(int)duration+" сек");
   File chunk=new File(work,"source.mp4");chunk.delete();
   ff(Arrays.asList("-y","-ss",String.valueOf(start),"-i",src.getAbsolutePath(),"-t",String.valueOf(end-start),"-map","0:v:0","-map","0:a:0?","-c:v","libx264","-preset","ultrafast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",chunk.getAbsolutePath()));
   if(!chunk.isFile()||chunk.length()<1024)throw new IOException("Не удалось прочитать фрагмент видео из галереи");
   analyze(chunk,start,end-start);cursor=end;chunk.delete();
  }
 }
 private static JSONObject galleryArgs(JSONObject a)throws Exception{
  if(a.optString("local").isEmpty())return a;
  if(!new File(a.optString("local")).isFile())throw new IllegalArgumentException("Файл из галереи не найден");
  return new JSONObject(a.toString()).put("url","https://www.youtube.com/");
 }
"""
patch(svc,[
 ('public static void validate(JSONObject a)throws Exception{','public static void validate(JSONObject a)throws Exception{a=galleryArgs(a);'),
 ('.put("url",args.getString("url"))','.put("url",args.optString("url",args.optString("local")))'),
 ('YoutubeDL.getInstance().init(this);FFmpeg.getInstance().init(this);',
  'YoutubeDL.getInstance().init(this);FFmpeg.getInstance().init(this);\n   if(!args.optString("local").isEmpty()){File lf=new File(args.getString("local"));sourceKey="local:"+lf.getName()+":"+System.currentTimeMillis();phase("starting","Видео из галереи: "+lf.getName());localFile(lf);phase(stopping?"stopped":"complete",stopping?"Остановлено. Готовые клипы сохранены.":"Обработка завершена");return;}'),
 (' private String safeError(Throwable e)',LOCAL_METHOD+' private String safeError(Throwable e)'),
],'ClipsService.java')

# 4) UI: button + handler
JS=r"""/* AYT_GALLERY */
window.clipsLocal=async function(){const val=id=>document.getElementById(id).value;try{if(!document.getElementById('clip-rights').checked)throw new Error('Подтвердите право на использование материала');const path=await native('pickVideo');if(!path)return;const a={local:path,length:Number(val('clip-length')),maxClips:Number(val('clip-count')),layout:val('clip-layout'),focus:Number(val('clip-focus-range'))/100,language:val('clip-language'),strict:document.getElementById('clip-strict').checked};for(const k of ['cameraX','cameraY','cameraW','cameraH'])a[k]=Number(val(k))/100;if(a.layout==='split'&&(a.cameraX+a.cameraW>1||a.cameraY+a.cameraH>1))throw new Error('Область веб-камеры выходит за границы видео');await native('clips.start',a);state.phase='starting';state.message='Видео из галереи: запуск обработки';paint();setTimeout(refresh,600);}catch(err){toast(err.message||String(err));}};
"""
patch(root/'assets/clips.js',[
 ('<button class="btn primary block" id="clip-start" type="submit">✂ Начать нарезку</button>',
  '<button class="btn primary block" id="clip-start" type="submit">✂ Начать нарезку</button><button type="button" class="btn ghost block" id="clip-local" onclick="clipsLocal()" style="margin-top:8px">📁 Нарезать видео из галереи</button>'),
 ('window.clipsStop=',JS+'window.clipsStop='),
],'assets/clips.js')
print('[gallery] done')
