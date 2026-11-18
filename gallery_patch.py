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


# ================= AYT_V4: faster speech, visible progress, subtitle previews =================
V4='AYT_V4'
def patch4(path,pairs,name,prefix=''):
    s=path.read_text(encoding='utf-8')
    if V4 in s: print('[v4] already:',name);return
    for old,new,req in pairs:
        if old in s: s=s.replace(old,new,1)
        elif req: raise AssertionError(f'[v4] anchor not found in {name}: {old[:60]!r}')
        else: print('[v4] optional skipped in',name,':',old[:50])
    path.write_text(prefix+s,encoding='utf-8');print('[v4] patched:',name)

# Whisper: greedy without temperature fallback (big speedup on phones)
patch4(root/'android/app/src/main/cpp/bridge.cpp',[
 ('p.no_context=true;','p.no_context=true;p.greedy.best_of=1;p.temperature_inc=0.0f;p.suppress_blank=true;',True),
],'bridge.cpp','// AYT_V4\n')

# Java: shorter windows (first clips sooner), 4 big-core threads, progress text with time range
patch4(root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsService.java',[
 ('WINDOW=300,OVERLAP=15','WINDOW=180,OVERLAP=10',False),
 ('Math.max(2,Math.min(8,Runtime.getRuntime().availableProcessors()))','Math.max(2,Math.min(4,Runtime.getRuntime().availableProcessors()))',False),
 ('phase("rendering","Распознаю речь и ищу кандидатов на нарезку");',
  'phase("rendering","Распознаю речь "+String.format(Locale.US,"%d:%02d–%d:%02d",(int)origin/60,(int)origin%60,(int)(origin+duration)/60,(int)(origin+duration)%60)+" · ищу моменты"); /* AYT_V4 */',False),
],'ClipsService.java','// AYT_V4\n')

PREVIEW_JS=r"""/* AYT_V4 subtitle previews */
(function(){
const O='-2px -2px 0 #111,2px -2px 0 #111,-2px 2px 0 #111,2px 2px 0 #111,0 2px 3px rgba(0,0,0,.6)';
const ST={classic:{n:'Классика',c:'color:#fff;font-weight:800;text-shadow:'+O},
 yellow:{n:'Жёлтые',c:'color:#ffe600;font-weight:900;text-shadow:'+O},
 box:{n:'Плашка',c:'color:#fff;font-weight:800;background:rgba(0,0,0,.7);padding:1px 6px;border-radius:4px'},
 neon:{n:'Неон',c:'color:#00ffff;font-weight:900;text-shadow:-1px -1px 0 #ff00ff,1px 1px 0 #ff00ff,0 0 6px #ff00ff,0 0 12px #ff00ff'},
 center:{n:'По центру',c:'color:#fff;font-weight:900;text-shadow:'+O,mid:1},
 minimal:{n:'Минимал',c:'color:#fff;font-weight:500;text-shadow:1px 2px 4px rgba(0,0,0,.85)'}};
const SZ={s:{n:'S',px:38},m:{n:'M',px:48},l:{n:'L',px:62},xl:{n:'XL',px:76}};
const CSS='<style id="ayt-sp-css">.ayt-sp{display:flex;gap:12px;align-items:flex-start;margin:10px 0 14px}.ayt-sp-frame{flex:0 0 120px;height:213px;border-radius:14px;position:relative;overflow:hidden;background:linear-gradient(160deg,#5b6b8c 0%,#2a2f45 55%,#151826 100%);box-shadow:0 4px 14px rgba(0,0,0,.35)}.ayt-sp-frame:before{content:"";position:absolute;left:18%;top:22%;width:64%;height:34%;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 70%)}.ayt-sp-line{position:absolute;left:6px;right:6px;bottom:20%;text-align:center;line-height:1.15;font-family:Arial,Roboto,sans-serif}.ayt-sp-line.mid{bottom:auto;top:50%;transform:translateY(-50%)}.ayt-sp-side{flex:1;min-width:0}.ayt-sp-lab{font-size:12px;opacity:.75;margin:0 0 6px}.ayt-sp-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}.ayt-sp-tiles.sz{grid-template-columns:repeat(4,1fr)}.ayt-sp-t{border:2px solid transparent;border-radius:10px;padding:8px 2px 4px;background:linear-gradient(135deg,#3a4160,#1b1e2b);color:#fff;display:flex;flex-direction:column;align-items:center;gap:3px;cursor:pointer}.ayt-sp-t small{font-size:10px;opacity:.8;font-weight:500;text-shadow:none;color:#fff}.ayt-sp-t.on{border-color:#ff4d4d;box-shadow:0 0 0 2px rgba(255,77,77,.25)}</style>';
function setup(){const box=document.getElementById('clip-sub-preview'),ss=document.getElementById('clip-sub-style'),sz=document.getElementById('clip-sub-size');if(!box||!ss||!sz||box.dataset.ok)return;box.dataset.ok=1;if(!document.getElementById('ayt-sp-css'))document.head.insertAdjacentHTML('beforeend',CSS);ss.closest('.clip-grid').style.display='none';
 function render(){const st=ST[ss.value]||ST.classic,z=SZ[sz.value]||SZ.m;
  box.innerHTML='<div class="ayt-sp"><div class="ayt-sp-frame"><div class="ayt-sp-line'+(st.mid?' mid':'')+'"><span style="'+st.c+';font-size:'+(z.px/6).toFixed(1)+'px">Вот это был момент!</span></div></div><div class="ayt-sp-side"><p class="ayt-sp-lab">Стиль субтитров</p><div class="ayt-sp-tiles">'+
  Object.keys(ST).map(k=>'<button type="button" class="ayt-sp-t'+(k===ss.value?' on':'')+'" data-st="'+k+'"><span style="'+ST[k].c+';font-size:13px">Текст</span><small>'+ST[k].n+'</small></button>').join('')+
  '</div><p class="ayt-sp-lab">Размер</p><div class="ayt-sp-tiles sz">'+
  Object.keys(SZ).map(k=>'<button type="button" class="ayt-sp-t'+(k===sz.value?' on':'')+'" data-sz="'+k+'"><span style="'+st.c+';font-size:'+(8+SZ[k].px/6).toFixed(0)+'px">Аа</span><small>'+SZ[k].n+'</small></button>').join('')+'</div></div></div>';
  box.querySelectorAll('[data-st]').forEach(b=>b.onclick=()=>{ss.value=b.dataset.st;if(ss.onchange)ss.onchange();render();});
  box.querySelectorAll('[data-sz]').forEach(b=>b.onclick=()=>{sz.value=b.dataset.sz;if(sz.onchange)sz.onchange();render();});}
 render();setTimeout(render,900);}
setInterval(setup,500);
})();
"""
patch4(root/'assets/clips.js',[
 ('\n <label for="clip-language">','<div id="clip-sub-preview"></div>\n <label for="clip-language">',True),
 ('window.clipsStop=',PREVIEW_JS+'window.clipsStop=',True),
],'assets/clips.js','/* AYT_V4 */\n')
print('[v4] done')


# ================= AYT_V5: drop (Music)/[Музыка] captions, webcam position presets =================
V5='AYT_V5'
def patch5(path,pairs,name,prefix):
    s=path.read_text(encoding='utf-8')
    if V5 in s: print('[v5] already:',name);return
    for old,new in pairs:
        assert old in s, f'[v5] anchor not found in {name}: {old[:60]!r}'
        s=s.replace(old,new,1)
    path.write_text(prefix+s,encoding='utf-8');print('[v5] patched:',name)

PH='phrases.add(new ClipLogic.Phrase(x.getDouble("start"),x.getDouble("end"),x.getString("text")));'
PH_NEW=('{String tx=x.getString("text").replaceAll("[\\\\[\\\\(\\\\*][^\\\\]\\\\)\\\\*]{0,40}[\\\\]\\\\)\\\\*]"," ").replaceAll("[♪♫♬]"," ").replaceAll("\\\\s+"," ").trim();'
        'if(tx.replaceAll("[^\\\\p{L}\\\\p{N}]","").length()>=2)phrases.add(new ClipLogic.Phrase(x.getDouble("start"),x.getDouble("end"),tx));} /* AYT_V5 */')
patch5(root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsService.java',[(PH,PH_NEW)],'ClipsService.java','// AYT_V5\n')

CAM_ANCHOR='<div id="clip-camera" hidden><p class="clip-note">'
CAM_UI=('<div id="clip-camera" hidden><p class="clip-note">Где вебка стримера на экране:</p>'
 '<div class="clip-grid" style="grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">'
 '<button type="button" class="btn ghost sm" onclick="clipsCam(0,0)">↖ Слева сверху</button>'
 '<button type="button" class="btn ghost sm" onclick="clipsCam(1,0)">↗ Справа сверху</button>'
 '<button type="button" class="btn ghost sm" onclick="clipsCam(0,1)">↙ Слева снизу</button>'
 '<button type="button" class="btn ghost sm" onclick="clipsCam(1,1)">↘ Справа снизу</button></div><p class="clip-note">')
CAM_JS=r"""/* AYT_V5 */
window.clipsCam=function(r,b){const w=25,h=28,set=(k,v)=>{const el=document.getElementById(k);if(el)el.value=v;};set('cameraW',w);set('cameraH',h);set('cameraX',r?100-w:0);set('cameraY',b?100-h:0);toast('Область вебки выставлена. При нужде подправьте цифры.');};
"""
patch5(root/'assets/clips.js',[(CAM_ANCHOR,CAM_UI),('window.clipsStop=',CAM_JS+'window.clipsStop=')],'assets/clips.js','/* AYT_V5 */\n')
print('[v5] done')
