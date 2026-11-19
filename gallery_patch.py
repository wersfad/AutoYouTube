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


# ================= AYT_V6: live Twitch never fails on backlog, skips to fresh segments =================
svc6=root/'android/app/src/main/java/com/wersfad/autoyoutube/ClipsService.java'
s6=svc6.read_text(encoding='utf-8')
if 'AYT_V6' not in s6:
    old='if(completed-next>6)throw new IOException("Телефон не успевает обрабатывать эфир: накопилось больше 12 минут. Готовые клипы сохранены.");'
    new=('if(completed-next>2){for(int k=next;k<completed-1;k++)new File(dir,String.format(Locale.US,"part-%06d.ts",k)).delete();next=completed-1;'
         'phase("live","Телефон не успевает за эфиром: пропускаю старые фрагменты и беру свежие");} /* AYT_V6 */')
    assert old in s6,'[v6] live backlog anchor not found in ClipsService.java'
    s6=s6.replace(old,new,1)
    svc6.write_text('// AYT_V6\n'+s6,encoding='utf-8');print('[v6] patched: ClipsService.java')
print('[v6] done')


# ================= AYT_V7: SYNTX AI opened inside the app (in-app browser, user's own account) =================
nd=root/'lib/native.dart';s7=nd.read_text(encoding='utf-8')
if 'AYT_V7' not in s7:
    old="case 'open':"
    assert old in s7,'[v7] open anchor not found in native.dart'
    s7=s7.replace(old,"case 'openInApp': // AYT_V7\n        await launchUrl(Uri.parse(a['url'].toString()), mode: LaunchMode.inAppBrowserView);\n        return true;\n      "+old,1)
    nd.write_text(s7,encoding='utf-8');print('[v7] patched: native.dart')
cj=root/'assets/clips.js';c7=cj.read_text(encoding='utf-8')
if 'AYT_V7' not in c7:
    anchor='<div id="clip-status" aria-live="polite"></div>'
    assert anchor in c7,'[v7] status anchor not found in clips.js'
    card=('<section class="glass card clip-model"><div><h3>✨ Нарезка через SYNTX AI</h3><p>Откроется внутри приложения. Нужен ваш аккаунт SYNTX и их токены. Задача скопируется — просто вставьте её.</p></div>'
          '<button type="button" class="btn ghost sm" onclick="clipsSyntx()">Открыть</button></section>\n ')
    c7=c7.replace(anchor,card+anchor,1)
    js=r"""/* AYT_V7 */
window.clipsSyntx=async function(){const n=(document.getElementById('clip-count')||{}).value||10,l=(document.getElementById('clip-length')||{}).value||45;
 const prompt='Сделай '+n+' вертикальных нарезок 9:16 по ~'+l+' секунд с субтитрами. Бери только самые крутые и интересные моменты: яркие реакции, смешное, неожиданное, кульминации. Без скучных и проходных частей.';
 try{await navigator.clipboard.writeText(prompt);toast('Задача скопирована — вставьте её в SYNTX');}catch(e){}
 try{await native('openInApp',{url:'https://syntx.ai/ru'});}catch(err){toast(err.message||String(err));}};
"""
    c7=c7.replace('window.clipsStop=',js+'window.clipsStop=',1)
    cj.write_text('/* AYT_V7 */\n'+c7,encoding='utf-8');print('[v7] patched: clips.js')
print('[v7] done')


# ================= AYT_V8: smarter moments, layout templates, sharp webcam, streamer voice, faster =================
import base64 as _b64
APP=root/'android/app/src/main/java/com/wersfad/autoyoutube'
(APP/'ClipLogic.java').write_text(_b64.b64decode("cGFja2FnZSBjb20ud2Vyc2ZhZC5hdXRveW91dHViZTsKaW1wb3J0IGphdmEudXRpbC4qOwoKLyoqIEFZVF9WODogbW9tZW50IHNlbGVjdGlvbiB0dW5lZCBmb3Igc3RyZWFtczogbG91ZCBidXJzdHMsIHN1ZGRlbiBqdW1wcywgZmFzdCBlbW90aW9uYWwgc3BlZWNoLCByZWFjdGlvbiB3b3JkcywgaG9vay1maXJzdCB3aW5kb3dzLiAqLwpwdWJsaWMgZmluYWwgY2xhc3MgQ2xpcExvZ2ljIHsKIHB1YmxpYyBzdGF0aWMgZmluYWwgY2xhc3MgUGhyYXNlIHsKICBwdWJsaWMgZmluYWwgZG91YmxlIHN0YXJ0LGVuZDsgcHVibGljIGZpbmFsIFN0cmluZyB0ZXh0OwogIHB1YmxpYyBQaHJhc2UoZG91YmxlIHMsZG91YmxlIGUsU3RyaW5nIHQpe3N0YXJ0PXM7ZW5kPWU7dGV4dD10O30KIH0KIHB1YmxpYyBzdGF0aWMgZmluYWwgY2xhc3MgTW9tZW50IHsKICBwdWJsaWMgZmluYWwgZG91YmxlIHN0YXJ0LGVuZCxzY29yZTsgcHVibGljIGZpbmFsIFN0cmluZyByZWFzb247CiAgTW9tZW50KGRvdWJsZSBzLGRvdWJsZSBlLGRvdWJsZSBxLFN0cmluZyByKXtzdGFydD1zO2VuZD1lO3Njb3JlPXE7cmVhc29uPXI7fQogfQogcHVibGljIHN0YXRpYyBib29sZWFuIG92ZXJsYXBzKGRvdWJsZSBhLGRvdWJsZSBiLGRvdWJsZSBjLGRvdWJsZSBkKXtyZXR1cm4gTWF0aC5tYXgoYSxjKTxNYXRoLm1pbihiLGQpO30KIHB1YmxpYyBzdGF0aWMgYm9vbGVhbiBhbGxvd2VkSG9zdChTdHJpbmcgaG9zdCl7cmV0dXJuIGhvc3QhPW51bGwmJkFycmF5cy5hc0xpc3QoInlvdXR1YmUuY29tIiwid3d3LnlvdXR1YmUuY29tIiwibS55b3V0dWJlLmNvbSIsInlvdXR1LmJlIiwidHdpdGNoLnR2Iiwid3d3LnR3aXRjaC50diIsIm0udHdpdGNoLnR2IikuY29udGFpbnMoaG9zdC50b0xvd2VyQ2FzZShMb2NhbGUuUk9PVCkpO30KIHByaXZhdGUgc3RhdGljIGZpbmFsIFN0cmluZ1tdIFNUUk9ORz17ItC90LUg0LzQvtC20LXRgiDQsdGL0YLRjCIsItC+0YTQuNCz0LXRgtGMIiwi0L7RhdGA0LXQvdC10YLRjCIsItC+0YXRg9C10YLRjCIsItC/0LjQt9C00LXRhiIsItC10LHQsNGC0YwiLCLQvdC40YXRg9GPIiwi0LDRhdGD0LXRgtGMIiwi0LTQsCDQu9Cw0LTQvdC+Iiwi0LrQsNC6INGC0LDQuiIsItGH0YLQviDQt9CwIiwi0L3QtdCy0LXRgNC+0Y/RgtC90L4iLCLQutCw0L/QtdGGIiwi0LbQtdGB0YLRjCIsItCy0LDRgyIsItC+0LPQviIsItC+0LHQsNC70LTQtdGC0YwiLCLQv9C+0LHQtdC00LAiLCLQstGL0LjQs9GA0LDQuyIsItCy0YvQuNCz0YDQsNC70LgiLCLQv9GA0L7QuNCz0YDQsNC7Iiwi0LrQu9Cw0YLRhyIsItC40LzQsdCwIiwi0LLQsNC90YjQvtGCIiwibm8gd2F5Iiwid2hhdCB0aGUiLCJvaCBteSBnb2QiLCJvbWciLCJsZXQncyBnbyIsImxldHMgZ28iLCJpbnNhbmUiLCJ1bmJlbGlldmFibGUiLCJjbHV0Y2giLCJob2x5Iiwid3RmIn07CiBwcml2YXRlIHN0YXRpYyBmaW5hbCBTdHJpbmdbXSBNRURJVU09eyLRgdC80L7RgtGA0LgiLCLRgdC80L7RgtGA0LjRgtC1Iiwi0LHQu9C40L0iLCLQsdC70Y8iLCLQvdC40YTQuNCz0LAiLCLQtNCw0LLQsNC5Iiwi0L/QvtCz0L3QsNC70LgiLCLRgdGC0L7QvyIsItC/0L7QtNC+0LbQtNC4Iiwi0L3QtdGCINC90LXRgiIsItC00LAg0LTQsCIsItC60YDQsNGB0LDQstCwIiwi0LrRgNCw0YHQuNCy0L4iLCLQutGA0LjQvdC2Iiwi0YDQvtGE0LsiLCLQu9C+0LsiLCLQutC10LoiLCLQsNGF0LDRhSIsItGF0LDRhdCwIiwi0YXQsNGFIiwi0YHQvNC10YjQvdC+Iiwi0YHRgtGA0LDRiNC90L4iLCLQv9C+0LzQvtCz0LjRgtC1Iiwi0LHQtdCz0LgiLCLQsdC10LbQuNC8Iiwi0YPQsdC40LvQuCIsItGD0LHQuNC7Iiwi0YPQvNC10YAiLCLQv9C+0YHQu9C10LTQvdC40LkiLCLQs9C+0YHQv9C+0LTQuCIsItCx0L7QttC1Iiwi0YPRgNCwIiwieWVzIiwibm8gbm8iLCJydW4iLCJkdWRlIiwiYnJvIiwiY3JhenkiLCJmdW5ueSJ9Owogc3RhdGljIGRvdWJsZSBrZXlTY29yZShTdHJpbmcgdCl7ZG91YmxlIGs9MDtmb3IoU3RyaW5nIHc6U1RST05HKWlmKHQuY29udGFpbnModykpays9Mjtmb3IoU3RyaW5nIHc6TUVESVVNKWlmKHQuY29udGFpbnModykpays9MTtpZih0Lm1hdGNoZXMoIi4qKNGF0LApezIsfS4qIil8fHQubWF0Y2hlcygiLiooYWh8aGEpezIsfS4qIikpays9MS41O3JldHVybiBNYXRoLm1pbig2LGspO30KIHN0YXRpYyBpbnQgd29yZHMoU3RyaW5nIHQpe2ludCBjPTA7Zm9yKFN0cmluZyB3OnQudHJpbSgpLnNwbGl0KCJcXHMrIikpaWYody5yZXBsYWNlQWxsKCJbXlxccHtMfVxccHtOfV0iLCIiKS5sZW5ndGgoKT4wKWMrKztyZXR1cm4gYzt9CiBzdGF0aWMgU3RyaW5nIGN1dChTdHJpbmcgdCl7dD10LnJlcGxhY2VBbGwoIlxccysiLCIgIikudHJpbSgpO3JldHVybiB0Lmxlbmd0aCgpPjQwP3Quc3Vic3RyaW5nKDAsNDApKyLigKYiOnQ7fQogcHVibGljIHN0YXRpYyBMaXN0PE1vbWVudD4gc2VsZWN0KExpc3Q8UGhyYXNlPiBwaHJhc2VzLGZsb2F0W10gYXVkaW8saW50IHJhdGUsZG91YmxlIGR1cmF0aW9uLGRvdWJsZSBsZW5ndGgsYm9vbGVhbiBzdHJpY3QpewogIExpc3Q8TW9tZW50PiBvdXQ9bmV3IEFycmF5TGlzdDw+KCk7CiAgaWYoZHVyYXRpb248TWF0aC5taW4oMTIsbGVuZ3RoKXx8YXVkaW8ubGVuZ3RoPT0wKXJldHVybiBvdXQ7CiAgaW50IG49KGludClNYXRoLmNlaWwoYXVkaW8ubGVuZ3RoLyhkb3VibGUpcmF0ZSk7ZG91YmxlW10gcm1zPW5ldyBkb3VibGVbbl07CiAgZm9yKGludCBpPTA7aTxhdWRpby5sZW5ndGg7aSsrKXtkb3VibGUgdj1hdWRpb1tpXTtybXNbaS9yYXRlXSs9dip2O30KICBmb3IoaW50IGk9MDtpPG47aSsrKXtpbnQgY250PU1hdGgubWluKHJhdGUsYXVkaW8ubGVuZ3RoLWkqcmF0ZSk7cm1zW2ldPU1hdGguc3FydChybXNbaV0vTWF0aC5tYXgoMSxjbnQpKTt9CiAgZG91YmxlW10gc289cm1zLmNsb25lKCk7QXJyYXlzLnNvcnQoc28pO2RvdWJsZSBtZWQ9TWF0aC5tYXgoMWUtNCxzb1tzby5sZW5ndGgvMl0pLHA5MD1zb1tNYXRoLm1pbihzby5sZW5ndGgtMSwoaW50KShzby5sZW5ndGgqMC45KSldOwogIGRvdWJsZSB0b3RhbFdvcmRzPTA7Zm9yKFBocmFzZSBwOnBocmFzZXMpdG90YWxXb3Jkcys9d29yZHMocC50ZXh0KTtkb3VibGUgYXZnUmF0ZT10b3RhbFdvcmRzL01hdGgubWF4KDEsZHVyYXRpb24pOwogIGRvdWJsZVtdIGV4PW5ldyBkb3VibGVbbl07CiAgZm9yKGludCBpPTA7aTxuO2krKyl7ZG91YmxlIGxvdWQ9cm1zW2ldL21lZDtkb3VibGUganVtcD1pPjA/TWF0aC5tYXgoMCxybXNbaV0tcm1zW2ktMV0pL21lZDowO2V4W2ldPU1hdGgubWF4KDAsbG91ZC0xLjQpKjEuMitNYXRoLm1pbigzLGp1bXApKjAuODt9CiAgZm9yKFBocmFzZSBwOnBocmFzZXMpe1N0cmluZyB0PXAudGV4dC50b0xvd2VyQ2FzZShMb2NhbGUuUk9PVCk7ZG91YmxlIGR1cj1NYXRoLm1heCguMyxwLmVuZC1wLnN0YXJ0KTtkb3VibGUgcj13b3Jkcyh0KS9kdXI7CiAgIGRvdWJsZSBmYXN0PWF2Z1JhdGU+MD9NYXRoLm1heCgwLHIvTWF0aC5tYXgoMS41LGF2Z1JhdGUpLTEuMik6MDsKICAgZG91YmxlIGFkZD1rZXlTY29yZSh0KSoxLjUrTWF0aC5taW4oMixmYXN0KSsodC5jb250YWlucygiISIpPzAuNjowKTsKICAgZm9yKGludCBzPU1hdGgubWF4KDAsKGludClwLnN0YXJ0KTtzPD1NYXRoLm1pbihuLTEsKGludClwLmVuZCk7cysrKWV4W3NdKz1hZGQ7fQogIGRvdWJsZVtdIHNtPW5ldyBkb3VibGVbbl07Zm9yKGludCBpPTA7aTxuO2krKyl7ZG91YmxlIHM9MDtpbnQgYz0wO2ZvcihpbnQgaj1NYXRoLm1heCgwLGktMSk7ajw9TWF0aC5taW4obi0xLGkrMSk7aisrKXtzKz1leFtqXTtjKys7fXNtW2ldPXMvYzt9CiAgTGlzdDxNb21lbnQ+IGNhbmQ9bmV3IEFycmF5TGlzdDw+KCk7CiAgZm9yKGludCBpPTA7aTxuO2krKyl7CiAgIGlmKHNtW2ldPD0wKWNvbnRpbnVlO2Jvb2xlYW4gbG9jYWw9dHJ1ZTtmb3IoaW50IGo9TWF0aC5tYXgoMCxpLTQpO2o8PU1hdGgubWluKG4tMSxpKzQpO2orKylpZihzbVtqXT5zbVtpXSlsb2NhbD1mYWxzZTtpZighbG9jYWwpY29udGludWU7CiAgIGRvdWJsZSBzPU1hdGgubWF4KDAsaS1sZW5ndGgqMC4zNSksZT1NYXRoLm1pbihkdXJhdGlvbixzK2xlbmd0aCk7cz1NYXRoLm1heCgwLGUtbGVuZ3RoKTsKICAgZm9yKFBocmFzZSBwOnBocmFzZXMpe2lmKHAuc3RhcnQ8cyYmcC5lbmQ+cyYmcy1wLnN0YXJ0PDQpcz1wLnN0YXJ0O2lmKHAuc3RhcnQ8ZSYmcC5lbmQ+ZSYmcC5lbmQtZTw0KWU9TWF0aC5taW4oZHVyYXRpb24scC5lbmQpO30KICAgaWYoZS1zPDEyKWNvbnRpbnVlOwogICBkb3VibGUgc3VtPTAscXVpZXQ9MDtpbnQgc2Vjcz0wO2ZvcihpbnQgaj0oaW50KXM7ajxNYXRoLm1pbihuLChpbnQpTWF0aC5jZWlsKGUpKTtqKyspe3N1bSs9c21bal07aWYocm1zW2pdPG1lZCowLjUpcXVpZXQrKztzZWNzKys7fQogICBpbnQgdz0wO1N0cmluZyBoaXQ9bnVsbDtmb3IoUGhyYXNlIHA6cGhyYXNlcylpZihvdmVybGFwcyhzLGUscC5zdGFydCxwLmVuZCkpe3crPXdvcmRzKHAudGV4dCk7aWYoaGl0PT1udWxsJiZrZXlTY29yZShwLnRleHQudG9Mb3dlckNhc2UoTG9jYWxlLlJPT1QpKT49MiloaXQ9cC50ZXh0O30KICAgZG91YmxlIHNjb3JlPXNtW2ldKjIrc3VtL01hdGgubWF4KDEsc2VjcykqMy0ocXVpZXQvTWF0aC5tYXgoMSxzZWNzKSkqMysodz49OD8wLjg6LTEuNSk7CiAgIFN0cmluZyByZWFzb249aGl0IT1udWxsPyLQrdC80L7RhtC40L7QvdCw0LvRjNC90LDRjyDRgNC10LDQutGG0LjRjzogwqsiK2N1dChoaXQpKyLCuyI6KHJtc1tpXT49cDkwPyLQk9GA0L7QvNC60LjQuSDQstGB0L/Qu9C10YHQuiAvINC60YDQuNC6Ijoi0JHRi9GB0YLRgNCw0Y8g0Y3QvNC+0YbQuNC+0L3QsNC70YzQvdCw0Y8g0YDQtdGH0YwiKTsKICAgY2FuZC5hZGQobmV3IE1vbWVudChzLGUsc2NvcmUscmVhc29uKSk7CiAgfQogIGNhbmQuc29ydCgoYSxiKS0+RG91YmxlLmNvbXBhcmUoYi5zY29yZSxhLnNjb3JlKSk7CiAgZG91YmxlIHRocj1zdHJpY3Q/NC41OjIuMjtpbnQgbWF4PXN0cmljdD8yOjM7CiAgZm9yKE1vbWVudCBtOmNhbmQpe2lmKG0uc2NvcmU8dGhyKWJyZWFrO2Jvb2xlYW4gZHVwPWZhbHNlO2ZvcihNb21lbnQgbzpvdXQpaWYob3ZlcmxhcHMobS5zdGFydCxtLmVuZCxvLnN0YXJ0LG8uZW5kKSlkdXA9dHJ1ZTtpZighZHVwKW91dC5hZGQobSk7aWYob3V0LnNpemUoKT49bWF4KWJyZWFrO30KICBpZihvdXQuaXNFbXB0eSgpJiYhc3RyaWN0JiYhY2FuZC5pc0VtcHR5KCkmJmNhbmQuZ2V0KDApLnNjb3JlPjEuMClvdXQuYWRkKGNhbmQuZ2V0KDApKTsKICBvdXQuc29ydChDb21wYXJhdG9yLmNvbXBhcmluZ0RvdWJsZSh4LT54LnN0YXJ0KSk7cmV0dXJuIG91dDsKIH0KIHByaXZhdGUgQ2xpcExvZ2ljKCl7fQp9Cg==").decode('utf-8'),encoding='utf-8');print('[v8] replaced: ClipLogic.java')
sv=APP/'ClipsService.java';s8=sv.read_text(encoding='utf-8')
if 'AYT_V8' not in s8:
    SPLIT='"split".equals(args==null?"":args.optString("layout"))'
    opt=[
     ('r.addOption("--force-keyframes-at-cuts");',''),
     ('r.addOption("--recode-video","mp4");',''),
     ('r.addOption("-f","bestvideo[height<=720]+bestaudio/best[height<=720]/best");','r.addOption("-f",'+SPLIT+'?"bestvideo[height<=1080]+bestaudio/best[height<=1080]/best":"bestvideo[height<=720]+bestaudio/best[height<=720]/best");'),
     ('r.addOption("-f","18/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best");','r.addOption("-f",'+SPLIT+'?"bestvideo[height<=1080]+bestaudio/best[height<=1080]/best":"18/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best");'),
     ('"-c:v","libx264","-preset","ultrafast","-crf","20","-c:a","aac","-b:a","128k",chunk.getAbsolutePath()','"-c","copy","-avoid_negative_ts","make_zero",chunk.getAbsolutePath()'),
     ('r.addOption("-f","best[height<=720]/best");','r.addOption("-f",'+SPLIT+'?"best[height<=1080]/best":"best[height<=720]/best");'),
     ('"-crf","23"','"-crf","20"'),
     ('"-vn","-ac","1","-ar","16000","-f","f32le"','"-vn","-af","highpass=f=100,lowpass=f=4000","-ac","1","-ar","16000","-f","f32le"'),
    ]
    for o,n in opt:
        if o in s8: s8=s8.replace(o,n)
        else: print('[v8] optional skipped:',o[:55])
    OLDF='scale=720:400:force_original_aspect_ratio=increase,crop=720:400[c];[game]scale=720:880:force_original_aspect_ratio=decrease,pad=720:880:(ow-iw)/2:(oh-ih)/2:black[g]'
    NEWF='scale=720:480:force_original_aspect_ratio=increase:flags=lanczos,crop=720:480,unsharp=5:5:0.5[c];[game]scale=720:800:force_original_aspect_ratio=increase:flags=lanczos,crop=720:800[g]'
    assert OLDF in s8,'[v8] split filter anchor not found'
    s8=s8.replace(OLDF,NEWF,1)
    SEL='List<ClipLogic.Moment> selected=ClipLogic.select('
    assert SEL in s8,'[v8] select anchor not found'
    VOICE=('if(phrases.size()>=4){double[] pr=new double[phrases.size()];for(int q=0;q<pr.length;q++){ClipLogic.Phrase ph=phrases.get(q);int a0=Math.max(0,(int)(ph.start*16000)),a1=Math.min(audio.length,(int)(ph.end*16000));double sq=0;for(int k=a0;k<a1;k++)sq+=audio[k]*audio[k];pr[q]=a1>a0?Math.sqrt(sq/(a1-a0)):0;}'
           'double[] so8=pr.clone();Arrays.sort(so8);double md8=so8[so8.length/2];List<ClipLogic.Phrase> keep8=new ArrayList<>();for(int q=0;q<pr.length;q++)if(pr[q]>=md8*0.45)keep8.add(phrases.get(q));phrases=keep8;} /* AYT_V8 streamer voice */\n  ')
    s8=s8.replace(SEL,VOICE+SEL,1)
    sv.write_text('// AYT_V8\n'+s8,encoding='utf-8');print('[v8] patched: ClipsService.java')
cj8=root/'assets/clips.js';c8=cj8.read_text(encoding='utf-8')
if 'AYT_V8' not in c8:
    a='<label for="clip-layout">'
    assert a in c8,'[v8] layout anchor not found'
    c8=c8.replace(a,'<div id="clip-layout-tiles"></div>'+a,1)
    c8=c8.replace('window.clipsStop=',r"""/* AYT_V8 layout templates */
(function(){
const T=[{k:'full',n:'Весь экран'},{k:'tl',n:'Вебка ↖',r:0,b:0},{k:'tr',n:'Вебка ↗',r:1,b:0},{k:'bl',n:'Вебка ↙',r:0,b:1},{k:'br',n:'Вебка ↘',r:1,b:1}];
const CSS='<style id="ayt-lt-css">#clip-camera{display:none!important}.ayt-lt-h{font-size:12px;opacity:.75;margin:8px 0 6px}.ayt-lt{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:10px}.ayt-lt-t{border:2px solid transparent;border-radius:10px;padding:6px 2px;background:rgba(255,255,255,.05);display:flex;flex-direction:column;align-items:center;gap:4px;color:inherit;cursor:pointer}.ayt-lt-t.on{border-color:#ff4d4d;background:rgba(255,77,77,.1)}.ayt-lt-src{width:44px;height:25px;border-radius:3px;background:linear-gradient(135deg,#3b6e4a,#1d3527);position:relative}.ayt-lt-src i{position:absolute;width:12px;height:8px;background:#ffcf5a;border-radius:2px}.ayt-lt-ph{width:40px;height:71px;border-radius:6px;overflow:hidden;display:flex;flex-direction:column;background:#111}.ayt-lt-cam{flex:0 0 37%;background:linear-gradient(160deg,#ffcf5a,#c9822b);display:flex;align-items:center;justify-content:center;font-size:13px}.ayt-lt-game{flex:1;background:linear-gradient(160deg,#4f8a5f,#1d3527);display:flex;align-items:center;justify-content:center;font-size:13px}.ayt-lt-t small{font-size:10px;opacity:.85;text-align:center;line-height:1.1}</style>';
function apply(t,silent){const sel=document.getElementById('clip-layout');if(!sel)return;sel.value=t.k==='full'?'portrait':'split';if(window.clipsLayout)clipsLayout(sel.value);if(t.k!=='full'){const w=25,h=28,set=(k,v)=>{const el=document.getElementById(k);if(el)el.value=v;};set('cameraW',w);set('cameraH',h);set('cameraX',t.r?100-w:0);set('cameraY',t.b?100-h:0);}localStorage.setItem('ayt-layout-tile',t.k);}
function setup(){const box=document.getElementById('clip-layout-tiles'),sel=document.getElementById('clip-layout');if(!box||!sel||box.dataset.ok)return;box.dataset.ok=1;if(!document.getElementById('ayt-lt-css'))document.head.insertAdjacentHTML('beforeend',CSS);const lab=sel.closest('label');if(lab)lab.style.display='none';
 const cur=()=>localStorage.getItem('ayt-layout-tile')||'full';
 function render(){const c=cur();box.innerHTML='<p class="ayt-lt-h">Шаблон кадра · где вебка у стримера</p><div class="ayt-lt">'+T.map(t=>{const corner=t.k==='full'?'':'<i style="'+(t.r?'right:2px;':'left:2px;')+(t.b?'bottom:2px':'top:2px')+'"></i>';const ph=t.k==='full'?'<div class="ayt-lt-ph"><div class="ayt-lt-game">🎮</div></div>':'<div class="ayt-lt-ph"><div class="ayt-lt-cam">🙂</div><div class="ayt-lt-game">🎮</div></div>';return '<button type="button" class="ayt-lt-t'+(t.k===c?' on':'')+'" data-k="'+t.k+'"><div class="ayt-lt-src">'+corner+'</div>'+ph+'<small>'+t.n+'</small></button>';}).join('')+'</div>';
  box.querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{apply(T.find(t=>t.k===b.dataset.k));render();});}
 const t0=T.find(t=>t.k===cur())||T[0];apply(t0,true);render();}
setInterval(setup,500);
})();
"""+'window.clipsStop=',1)
    cj8.write_text('/* AYT_V8 */\n'+c8,encoding='utf-8');print('[v8] patched: clips.js')
print('[v8] done')
