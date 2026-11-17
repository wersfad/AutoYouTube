#!/usr/bin/env python3
"""Fix for YouTube 403 / SABR in Clips: update yt-dlp on device, use clients
that still give direct links, and fall back to a full download + local cut."""
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
f = root / 'native/android/com/wersfad/autoyoutube/ClipsService.java'
s = f.read_text(encoding='utf-8')
DONE = 'AYT_YTDLP_FIX' in s

def rep(old, new):
    global s
    assert old in s, 'Anchor not found: ' + old[:60]
    s = s.replace(old, new, 1)


def apply_steps():
    # 1) update yt-dlp after init
    rep('YoutubeDL.getInstance().init(this);FFmpeg.getInstance().init(this);',
    'YoutubeDL.getInstance().init(this);FFmpeg.getInstance().init(this);updateYtdlp();')

    # 2) options for every yt-dlp call
    rep('r.addOption("--retries","2");ytdlpId=UUID',
    'r.addOption("--retries","3");r.addOption("--no-warnings");'
    'r.addOption("--extractor-args","youtube:player_client=android_vr,tv_simply,web_safari,default");'
    'ytdlpId=UUID')

    # 3) fallback when section download fails (403 etc.)
    rep('runYtdlp(r);if(!chunk.isFile())',
    'try{runYtdlp(r);}catch(Exception ex){if(stopping)throw ex;android.util.Log.w("AutoYouTubeClips","section download failed, fallback",ex);'
    'phase("starting","Прямая нарезка не удалась, скачиваю видео целиком и режу на телефоне");cutFromFull(url,chunk,start,end);}'
    'if(!chunk.isFile())')

    # 4) helper methods

helpers = r'''
 // AYT_YTDLP_FIX
 private void updateYtdlp(){
  SharedPreferences p=getSharedPreferences("clips_ytdlp",0);
  if(System.currentTimeMillis()-p.getLong("updated",0)<12L*3600*1000)return;
  phase("starting","Обновляю загрузчик видео (yt-dlp)");
  for(String ch:new String[]{"NIGHTLY","STABLE"}){
   try{
    Class<?> c=Class.forName("com.yausername.youtubedl_android.YoutubeDL$UpdateChannel");
    Object channel;
    try{channel=c.getField(ch).get(null);}catch(NoSuchFieldException e){channel=Class.forName(c.getName()+"$_"+ch).getField("INSTANCE").get(null);}
    java.lang.reflect.Method m=YoutubeDL.class.getMethod("updateYoutubeDL",Context.class,c);
    m.invoke(YoutubeDL.getInstance(),this,channel);
    p.edit().putLong("updated",System.currentTimeMillis()).apply();
    android.util.Log.i("AutoYouTubeClips","yt-dlp updated: "+ch);
    return;
   }catch(Throwable e){android.util.Log.w("AutoYouTubeClips","yt-dlp update "+ch+" failed",e);}
  }
 }
 private void cutFromFull(String url,File chunk,double start,double end)throws Exception{
  File full=new File(work,"full.mp4");
  if(!full.isFile()||full.length()<1024){
   YoutubeDLRequest r=new YoutubeDLRequest(url);
   r.addOption("-f","18/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best");
   r.addOption("--merge-output-format","mp4");
   r.addOption("-o",full.getAbsolutePath());
   runYtdlp(r);
   if(!full.isFile())throw new IOException("YouTube не отдал видео (403). Отключите VPN или попробуйте позже.");
  }
  ff(Arrays.asList("-y","-ss",String.valueOf(start),"-i",full.getAbsolutePath(),"-t",String.valueOf(end-start),
   "-c:v","libx264","-preset","ultrafast","-crf","20","-c:a","aac","-b:a","128k",chunk.getAbsolutePath()));
 }
'''
if not DONE:
    apply_steps()
    rep(' private JSONObject info(String url)throws Exception{', helpers + ' private JSONObject info(String url)throws Exception{')


# 5) robust model download (resume + retries + mirror)
if 'AYT_MODEL_FIX' not in s:
    a = s.index(' private void downloadModel()throws Exception{')
    b = s.index(' private void sleep(long ms)')
    s = s[:a] + r"""
 // AYT_MODEL_FIX
 private void downloadModel()throws Exception{
  phase("model","Загрузка модели речи (~75 МБ). Обработка будет на телефоне.");
  File temp=new File(model.getParentFile(),"tiny.part");
  String[] urls={"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin","https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"};
  Exception last=null;
  for(int attempt=0;attempt<10&&!model.isFile();attempt++){
   check();String src=urls[(attempt/3)%urls.length];long have=temp.isFile()?temp.length():0;
   HttpURLConnection c=null;
   try{
    c=(HttpURLConnection)new URL(src).openConnection();c.setInstanceFollowRedirects(true);c.setConnectTimeout(20000);c.setReadTimeout(60000);
    c.setRequestProperty("User-Agent","AutoYouTube/1.0");c.setRequestProperty("Accept-Encoding","identity");
    if(have>0)c.setRequestProperty("Range","bytes="+have+"-");
    int code=c.getResponseCode();
    if(code==416){have=temp.length();}
    else{
     if(code!=200&&code!=206)throw new IOException("HTTP "+code);
     boolean append=code==206&&have>0;if(!append)have=0;
     try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(temp,append)){byte[] buf=new byte[65536];int n;long total=have;
      while((n=in.read(buf))!=-1){check();out.write(buf,0,n);total+=n;if(total>100*1024*1024)throw new IOException("Неожиданный размер модели");
       if((total>>20)!=((total-n)>>20))phase("model","Загрузка модели: "+(total>>20)+" из ~75 МБ");}}
    }
    if(temp.length()<50*1024*1024)throw new IOException("Загружено "+(temp.length()>>20)+" МБ, продолжаю");
    try(DataInputStream in=new DataInputStream(new FileInputStream(temp))){if(Integer.reverseBytes(in.readInt())!=0x67676d6c){temp.delete();throw new IOException("Неверный формат модели Whisper");}}
    if(!temp.renameTo(model))throw new IOException("Не удалось сохранить модель");
   }catch(InterruptedException e){throw e;}
   catch(Exception e){last=e;android.util.Log.w("AutoYouTubeClips","model download attempt "+attempt,e);phase("model","Связь прервалась, докачиваю ("+(temp.length()>>20)+" МБ)…");sleep(3000);}
   finally{if(c!=null)c.disconnect();}
  }
  if(!model.isFile())throw new IOException("Не удалось скачать модель: "+(last==null?"":last.getMessage())+". Попробуйте выключить VPN.");
 }
""" + s[b:]

# 6) longer timeouts and more retries for slow / throttled connections
OLD_T = 'r.addOption("--socket-timeout","20");r.addOption("--retries","3");'
if '"--socket-timeout","60"' not in s:
    rep(OLD_T, 'r.addOption("--socket-timeout","60");r.addOption("--retries","10");'
        'r.addOption("--extractor-retries","5");r.addOption("--fragment-retries","10");'
        'r.addOption("--retry-sleep","linear=2::10");')

f.write_text(s, encoding='utf-8')
print('Clips fixes applied')

# 7) in-app YouTube sign-in (separate script, same folder)
import subprocess
subprocess.run([sys.executable, str(Path(__file__).with_name('login_patch.py')), str(root)], check=True)
