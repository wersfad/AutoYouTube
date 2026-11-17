#!/usr/bin/env python3
"""Fix for YouTube 403 / SABR in Clips: update yt-dlp on device, use clients
that still give direct links, and fall back to a full download + local cut."""
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
f = root / 'native/android/com/wersfad/autoyoutube/ClipsService.java'
s = f.read_text(encoding='utf-8')
if 'AYT_YTDLP_FIX' in s:
    print('yt-dlp fix already applied'); sys.exit(0)

def rep(old, new):
    global s
    assert old in s, 'Anchor not found: ' + old[:60]
    s = s.replace(old, new, 1)

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
rep(' private JSONObject info(String url)throws Exception{', helpers + ' private JSONObject info(String url)throws Exception{')
f.write_text(s, encoding='utf-8')
print('Applied yt-dlp / 403 fix to ClipsService.java')
