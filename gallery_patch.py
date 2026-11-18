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
print('[gallery] gallery source done')


# ================= AYT_EXTRAS: speed, save to gallery, subtitle styles =================
XM='AYT_EXTRAS'
def patch2(path,required,optional,name):
    s=path.read_text(encoding='utf-8')
    if XM in s:
        print('[extras] already patched:',name);return
    for old,new,cnt in required:
        assert old in s, f'[extras] anchor not found in {name}: {old[:70]!r}'
        s=s.replace(old,new) if cnt==0 else s.replace(old,new,cnt)
    for old,new in optional:
        if old in s: s=s.replace(old,new,1)
        else: print('[extras] optional anchor skipped in',name,':',old[:50])
    path.write_text(s,encoding='utf-8');print('[extras] patched:',name)

STYLE_METHOD=r"""
 // AYT_EXTRAS: subtitle templates
 private String assStyle(){int size;switch(args.optString("subSize","m")){case "s":size=38;break;case "l":size=62;break;case "xl":size=76;break;default:size=48;}
  String p="&H00FFFFFF",o="&H00101010",b="&H80000000";int bold=-1,border=1,outline=3,shadow=1,align=2,mv=230;
  switch(args.optString("subStyle","classic")){
   case "yellow":p="&H0000FFFF";outline=4;break;
   case "box":border=3;o="&HA0000000";outline=10;shadow=0;break;
   case "neon":p="&H00FFFF00";o="&H00FF00FF";outline=3;shadow=0;break;
   case "center":align=5;mv=0;outline=4;break;
   case "minimal":bold=0;outline=1;shadow=2;break;
  }
  return "Style: Main,Arial,"+size+","+p+",&H0000FFFF,"+o+","+b+","+bold+",0,0,0,100,100,0,0,"+border+","+outline+","+shadow+","+align+",45,45,"+mv+",1";
 }
"""
SVC=root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsService.java'
patch2(SVC,[
 (r'Style: Main,Arial,48,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,45,45,230,1\n', r'"+assStyle()+"\n',1),
 (' private String safeError(Throwable e)', STYLE_METHOD+' private String safeError(Throwable e)',1),
],[
 ('private static final int WINDOW=120,OVERLAP=20;','private static final int WINDOW=300,OVERLAP=15;'),
 ('Math.min(4,Runtime.getRuntime().availableProcessors())','Math.max(2,Math.min(8,Runtime.getRuntime().availableProcessors()))'),
 ('"-preset","ultrafast","-crf","23"','"-preset","ultrafast","-tune","fastdecode","-threads","0","-crf","23"'),
 ('"-c:v","libx264","-preset","ultrafast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",chunk.getAbsolutePath()));',
  '"-c","copy","-avoid_negative_ts","make_zero",chunk.getAbsolutePath()));'),
],'ClipsService.java')

SAVE_CASE=r"""case "clips.save":{ // AYT_EXTRAS
      JSONObject st=ClipsService.snapshot(activity);JSONArray cl=st.optJSONArray("clips");String cid=args.optString("id");String p=null;
      if(cl!=null)for(int i=0;i<cl.length();i++){JSONObject c=cl.getJSONObject(i);if(c.optString("id").equals(cid))p=c.optString("path");}
      if(p==null||!new File(p).isFile())throw new IllegalArgumentException("Клип не найден");
      if(Build.VERSION.SDK_INT<29)throw new IllegalStateException("Сохранение в галерею работает с Android 10. Используйте «Поделиться».");
      ContentValues v=new ContentValues();
      v.put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME,"AutoYouTube_"+System.currentTimeMillis()+".mp4");
      v.put(android.provider.MediaStore.MediaColumns.MIME_TYPE,"video/mp4");
      v.put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH,"Movies/AutoYouTube");
      v.put(android.provider.MediaStore.MediaColumns.IS_PENDING,1);
      ContentResolver cr=activity.getContentResolver();
      android.net.Uri uri=cr.insert(android.provider.MediaStore.Video.Media.EXTERNAL_CONTENT_URI,v);
      if(uri==null)throw new java.io.IOException("Галерея недоступна");
      try(java.io.InputStream in=new java.io.FileInputStream(p);java.io.OutputStream out=cr.openOutputStream(uri)){if(out==null)throw new java.io.IOException("Галерея недоступна");byte[] buf=new byte[65536];int n;while((n=in.read(buf))>0)out.write(buf,0,n);}
      catch(Exception ex){cr.delete(uri,null,null);throw ex;}
      v.clear();v.put(android.provider.MediaStore.MediaColumns.IS_PENDING,0);cr.update(uri,v,null,null);
      result.success("{\"saved\":true}");break;}
     case "clips.stop":"""
BR=root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsBridge.java'
patch2(BR,[('case "clips.stop":',SAVE_CASE,1)],[],'ClipsBridge.java')

SUB_UI='<div class="clip-grid"><label for="clip-sub-style">Стиль субтитров<select id="clip-sub-style"><option value="classic">Классика · белые</option><option value="yellow">Жёлтые с обводкой</option><option value="box">На тёмной плашке</option><option value="neon">Неон</option><option value="center">По центру экрана</option><option value="minimal">Минимал</option></select></label><label for="clip-sub-size">Размер субтитров<select id="clip-sub-size"><option value="s">Маленький</option><option value="m" selected>Средний</option><option value="l">Крупный</option><option value="xl">Очень крупный</option></select></label></div>\n <label for="clip-language">'
SAVE_JS=r"""/* AYT_EXTRAS */
window.clipsSave=async function(id){try{await native('clips.save',{id});toast('Сохранено в галерею: Movies/AutoYouTube');}catch(err){toast(err.message||String(err));}};
setInterval(()=>{for(const k of ['clip-sub-style','clip-sub-size']){const el=document.getElementById(k);if(el&&!el.dataset.ayt){el.dataset.ayt=1;const v=localStorage.getItem('ayt-'+k);if(v)el.value=v;el.onchange=()=>localStorage.setItem('ayt-'+k,el.value);}}},700);
"""
SHARE_BTN="""<button type="button" class="btn white block" onclick="clipsShare('${e(c.id)}')">"""
patch2(root/'assets/clips.js',[
 ('<label for="clip-language">',SUB_UI,1),
 ("strict:document.getElementById('clip-strict').checked}","strict:document.getElementById('clip-strict').checked,subStyle:val('clip-sub-style'),subSize:val('clip-sub-size')}",0),
 (SHARE_BTN,"""<button type="button" class="btn primary block" style="margin-bottom:8px" onclick="clipsSave('${e(c.id)}')">⬇ Скачать в галерею</button>"""+SHARE_BTN,1),
 ('window.clipsStop=',SAVE_JS+'window.clipsStop=',1),
],[],'assets/clips.js')

# AYT_EXTRAS: speech engine accepts 5-minute windows (was capped at 240 s) and up to 8 threads
cpp=root/'android/app/src/main/cpp/bridge.cpp'
assert cpp.exists(),'[extras] bridge.cpp not installed'
cs=cpp.read_text(encoding='utf-8')
if 'AYT_EXTRAS' not in cs:
    assert 'bytes>16000*4*240' in cs,'[extras] PCM limit anchor not found in bridge.cpp'
    cs=cs.replace('bytes>16000*4*240','bytes>16000*4*420',1)
    cs=cs.replace('std::min(4,int(threads))','std::min(8,int(threads))',1)
    cpp.write_text('// AYT_EXTRAS\n'+cs,encoding='utf-8');print('[extras] patched: bridge.cpp')
print('[extras] done')
