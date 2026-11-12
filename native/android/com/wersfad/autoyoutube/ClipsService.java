package com.wersfad.autoyoutube;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;
import com.yausername.youtubedl_android.*;
import com.yausername.ffmpeg.FFmpeg;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Experimental on-device pipeline. All media/ASR work is local, no processing server. */
public final class ClipsService extends Service {
 private static volatile ClipsService active;
 private static final Object LOCK=new Object();
 private static JSONObject state;
 private volatile boolean stopping=false;
 private volatile Process ffProcess;
 private Thread worker;
 private PowerManager.WakeLock wake;
 private File root,work,output,model;
 private JSONObject args,cursors;
 private String sourceKey="",ytdlpId="";
 private int maxClips,length;
 private static final int WINDOW=120,OVERLAP=20;
 public static boolean isActive(){return active!=null;}
 public static void validate(JSONObject a)throws Exception{
  URI u=new URI(a.optString("url"));
  if(!"https".equalsIgnoreCase(u.getScheme())||!ClipLogic.allowedHost(u.getHost())||u.getUserInfo()!=null||u.getPort()!=-1)throw new IllegalArgumentException("Нужна HTTPS-ссылка на YouTube или Twitch");
  if(a.optInt("length",45)<15||a.optInt("length",45)>60)throw new IllegalArgumentException("Длина: от 15 до 60 секунд");
  if(a.optInt("maxClips",10)<1||a.optInt("maxClips",10)>50)throw new IllegalArgumentException("Количество: от 1 до 50");
  if(a.optString("layout","portrait").equals("split"))for(String k:new String[]{"cameraX","cameraY","cameraW","cameraH"}){double n=a.optDouble(k,Double.NaN);if(!Double.isFinite(n)||n<0||n>1)throw new IllegalArgumentException("Укажите область веб-камеры в процентах");}
  if(a.optString("layout").equals("split")&&(a.optDouble("cameraW")<.05||a.optDouble("cameraH")<.05||a.optDouble("cameraX")+a.optDouble("cameraW")>1||a.optDouble("cameraY")+a.optDouble("cameraH")>1))throw new IllegalArgumentException("Область веб-камеры выходит за границы видео");
 }
 public static JSONObject snapshot(Context c){synchronized(LOCK){
  try{if(state==null){state=new JSONObject(c.getSharedPreferences("clips",0).getString("state","{}"));if(!state.has("clips"))state.put("clips",new JSONArray());if(!isActive()&&Arrays.asList("starting","history","live","waiting","rendering","model").contains(state.optString("phase")))state.put("phase","interrupted").put("message","Android прервал обработку. Можно запустить ссылку снова: сохранённые окна не повторяются.");}
   state.put("modelReady",new File(c.getFilesDir(),"clips/model/ggml-tiny.bin").isFile());
   return new JSONObject(state.toString());
  }catch(Exception e){return new JSONObject();}
 }}
 public static void requestStop(){ClipsService s=active;if(s!=null){s.stopping=true;YoutubeDL.getInstance().destroyProcessById(s.ytdlpId);Process p=s.ffProcess;if(p!=null)p.destroy();try{WhisperEngine.cancel();}catch(Throwable ignored){}}}
 @Override public IBinder onBind(Intent i){return null;}
 @Override public void onCreate(){super.onCreate();snapshot(this);root=new File(getFilesDir(),"clips");work=new File(root,"cache");output=new File(root,"output");model=new File(root,"model/ggml-tiny.bin");deleteTree(work);work.mkdirs();output.mkdirs();model.getParentFile().mkdirs();}
 @Override public int onStartCommand(Intent i,int flags,int id){
  if(i==null){stopSelf();return START_NOT_STICKY;}if(active!=null)return START_NOT_STICKY;
  active=this;stopping=false;
  NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
  if(Build.VERSION.SDK_INT>=26)nm.createNotificationChannel(new NotificationChannel("clips","Нарезки — обработка",NotificationManager.IMPORTANCE_LOW));
  startForeground(41,notification("Запуск обработки"));
  wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"autoyoutube:clips");wake.acquire(6*60*60*1000L);
  worker=new Thread(()->{try{
   args=new JSONObject(i.getStringExtra("args"));
   if("clips.model".equals(i.getStringExtra("command"))){downloadModel();phase("complete","Модель распознавания загружена");return;}
   validate(args);if(!model.isFile())throw new IOException("Сначала скачайте модель субтитров во вкладке «Нарезки»");
   length=args.optInt("length",45);maxClips=args.optInt("maxClips",10);
   synchronized(LOCK){state.put("jobCreated",0).put("url",args.getString("url")).put("scannedSeconds",0).put("phase","starting").put("message","Подключение к источнику");persist();}
   cursors=readJSON(new File(root,"coverage.json"));
   YoutubeDL.getInstance().init(this);FFmpeg.getInstance().init(this);
   String url=args.getString("url");JSONObject info=info(url);boolean live=info.optBoolean("is_live");
   sourceKey=(live?"twitch-live:":"video:")+info.optString("id",url);phase("starting",info.optString("title","Источник подключён"));
   boolean twitch=new URI(url).getHost().contains("twitch");
   if(live&&twitch){String archive=findCurrentArchive(url,info);if(archive!=null)archive(archive,true,url);else{phase("live","Прошлая часть эфира недоступна. Запись идёт с подключения, без восстановления прошлых моментов.");live(url,info);}}
   else if(live)throw new IOException("Для текущих эфиров пока поддерживается Twitch. YouTube — опубликованные видео.");
   else archive(url,false,url);
   phase(stopping?"stopped":"complete",stopping?"Остановлено. Готовые клипы сохранены.":"Обработка завершена");
  }catch(Throwable e){phase(stopping?"stopped":"error",stopping?"Остановлено. Готовые клипы сохранены.":safeError(e));}
  finally{requestStop();deleteTree(work);work.mkdirs();active=null;if(wake!=null&&wake.isHeld())wake.release();stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();}},"clips-worker");worker.start();return START_NOT_STICKY;
 }
 private String safeError(Throwable e){String t=e.getMessage();if(t==null)t=e.getClass().getSimpleName();return t.length()>900?t.substring(t.length()-900):t;}
 private Notification notification(String text){Intent stop=new Intent(this,ClipsStopReceiver.class);PendingIntent pi=PendingIntent.getBroadcast(this,0,stop,PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);return new Notification.Builder(this,"clips").setSmallIcon(getApplicationInfo().icon).setContentTitle("AutoYouTube · Нарезки").setContentText(text).setOngoing(true).addAction(new Notification.Action.Builder(null,"Остановить",pi).build()).build();}
 private void phase(String p,String text){synchronized(LOCK){try{state.put("phase",p).put("message",text).put("updatedAt",System.currentTimeMillis());persist();}catch(Exception ignored){}}((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(41,notification(text));}
 private void persist(){getSharedPreferences("clips",0).edit().putString("state",state.toString()).apply();}
 private void check()throws Exception{if(stopping)throw new InterruptedException("stopped");if(getUsableSpace()<400*1024*1024L)throw new IOException("Мало памяти: освободите минимум 400 МБ для временного кэша");}
 private long getUsableSpace(){return getFilesDir().getUsableSpace();}
 private String runYtdlp(YoutubeDLRequest r)throws Exception{check();r.addOption("--no-playlist");r.addOption("--socket-timeout","20");r.addOption("--retries","2");ytdlpId=UUID.randomUUID().toString();return YoutubeDL.getInstance().execute(r,ytdlpId,false,null).getOut();}
 private JSONObject info(String url)throws Exception{YoutubeDLRequest r=new YoutubeDLRequest(url);r.addOption("--dump-single-json");r.addOption("--skip-download");r.addOption("-f","best[height<=720]/best");String s=runYtdlp(r);for(String line:s.split("\n"))if(line.trim().startsWith("{"))return new JSONObject(line);throw new IOException("Источник не вернул сведения о видео");}
 private String findCurrentArchive(String url,JSONObject live)throws Exception{
  URI uri=new URI(url);String[] parts=uri.getPath().split("/");if(parts.length<2)return null;
  long started=live.optLong("timestamp",0);if(started<=0)return null;
  try{
   YoutubeDLRequest r=new YoutubeDLRequest("https://www.twitch.tv/"+parts[1]+"/videos?filter=archives&sort=time");r.addOption("--flat-playlist");r.addOption("--playlist-end","3");r.addOption("--dump-single-json");r.addOption("--skip-download");r.addOption("--socket-timeout","20");ytdlpId=UUID.randomUUID().toString();
   String json=YoutubeDL.getInstance().execute(r,ytdlpId,false,null).getOut();JSONObject listing=new JSONObject(json);JSONArray entries=listing.optJSONArray("entries");if(entries==null)return null;
   for(int n=0;n<entries.length();n++){JSONObject e=entries.getJSONObject(n);String target=e.optString("webpage_url",e.optString("url"));if(!target.startsWith("https://www.twitch.tv/videos/"))continue;JSONObject v=info(target);if(Math.abs(v.optLong("timestamp",0)-started)<180)return target;}
  }catch(Exception e){if(stopping)throw e;}
  return null;
 }
 private int created(){synchronized(LOCK){return state.optInt("jobCreated");}}
 private void archive(String url,boolean follow,String liveUrl)throws Exception{
  double cursor=cursors.optDouble(sourceKey,0);int unchanged=0;
  while(!stopping&&created()<maxClips){
   check();JSONObject meta=info(url);double duration=meta.optDouble("duration",0);if(duration<=0)throw new IOException("Не удалось определить доступную длительность записи");
   synchronized(LOCK){state.put("availableSeconds",duration).put("scannedSeconds",cursor);persist();}
   if(duration-cursor<12){if(!follow)break;phase("waiting","Прошлая часть разобрана. Жду новые фрагменты текущего эфира.");sleep(20000);boolean stillLive;try{stillLive=info(liveUrl).optBoolean("is_live");}catch(Exception e){if(stopping)throw e;stillLive=false;}
    if(!stillLive){unchanged++;if(unchanged>=3)break;}else unchanged=0;continue;}
   double start=Math.max(0,cursor-OVERLAP),end=Math.min(duration,Math.max(cursor,start)+WINDOW);if(end-start<12)break;
   phase(follow?"history":"starting","Получаю доступный фрагмент "+(int)start+"–"+(int)end+" сек");
   File chunk=new File(work,"source.mp4");deleteTree(chunk);for(File old:Objects.requireNonNull(work.listFiles()))if(old.getName().startsWith("source."))old.delete();
   YoutubeDLRequest r=new YoutubeDLRequest(url);r.addOption("-f","bestvideo[height<=720]+bestaudio/best[height<=720]/best");r.addOption("--download-sections","*"+(int)start+"-"+(int)end);r.addOption("--force-keyframes-at-cuts");r.addOption("--merge-output-format","mp4");r.addOption("--recode-video","mp4");r.addOption("-o",chunk.getAbsolutePath());runYtdlp(r);if(!chunk.isFile())throw new IOException("Видео не загружено. Источник может требовать вход или не поддерживать выбранный фрагмент.");
   analyze(chunk,start,end-start);cursor=end;cursors.put(sourceKey,cursor);writeJSON(new File(root,"coverage.json"),cursors);chunk.delete();
  }
 }
 private void live(String url,JSONObject meta)throws Exception{
  File dir=new File(work,"live");dir.mkdirs();
  // Continuous segmented capture, never disconnect between recognition/render operations.
  String media=meta.optString("url");if(!media.startsWith("https://"))throw new IOException("Не удалось получить доступный поток Twitch");
  double origin=meta.optLong("timestamp",0)>0?Math.max(0,System.currentTimeMillis()/1000.-meta.optLong("timestamp")):0;
  Process capture=startFF(Arrays.asList("-y","-i",media,"-map","0:v:0","-map","0:a:0?","-c","copy","-f","segment","-segment_time","120","-reset_timestamps","1","-segment_format","mpegts",new File(dir,"part-%06d.ts").getAbsolutePath()));
  ffProcess=capture;Thread drain=new Thread(()->{try{byte[] buf=new byte[4096];while(capture.getInputStream().read(buf)>=0){}}catch(Exception ignored){}});drain.start();
  int next=0;long lastProgress=System.currentTimeMillis();
  try{while(!stopping&&created()<maxClips){check();File[] files=dir.listFiles((d,n)->n.endsWith(".ts"));if(files==null)files=new File[0];Arrays.sort(files);boolean alive=capture.isAlive();int highest=-1;for(File f:files){String n=f.getName();highest=Math.max(highest,Integer.parseInt(n.substring(5,11)));}int completed=alive?highest:highest+1;
    if(completed-next>6)throw new IOException("Телефон не успевает обрабатывать эфир: накопилось больше 12 минут. Готовые клипы сохранены.");
    if(next<completed){File segment=new File(dir,String.format(Locale.US,"part-%06d.ts",next));double seconds=seconds(segment);if(seconds<2)throw new IOException("Пустой фрагмент потока");analyze(segment,origin+next*120,seconds);next++;lastProgress=System.currentTimeMillis();/* retain previous segment only until the current file has been analysed */segment.delete();}
    else if(!alive){if(capture.exitValue()!=0)throw new IOException("Поток Twitch завершился с ошибкой. Перезапустите ссылку; уже сохранённые клипы останутся.");break;}
    else{phase("waiting","Слежу за эфиром. Ожидаю завершения следующего фрагмента.");sleep(2500);if(System.currentTimeMillis()-lastProgress>240000)throw new IOException("Поток не отдаёт новые фрагменты. Проверьте подключение и повторите запуск.");}
  }}finally{capture.destroy();drain.join(3000);}
 }
 private void analyze(File source,double origin,double duration)throws Exception{
  check();phase("rendering","Распознаю речь и ищу кандидатов на нарезку");
  File pcm=new File(work,"audio.f32");ff(Arrays.asList("-y","-i",source.getAbsolutePath(),"-vn","-ac","1","-ar","16000","-f","f32le",pcm.getAbsolutePath()));
  JSONArray transcript=new JSONArray(WhisperEngine.decode(model.getAbsolutePath(),pcm.getAbsolutePath(),Math.min(4,Runtime.getRuntime().availableProcessors()),args.optString("language","auto")));
  List<ClipLogic.Phrase> phrases=new ArrayList<>();for(int i=0;i<transcript.length();i++){JSONObject x=transcript.getJSONObject(i);phrases.add(new ClipLogic.Phrase(x.getDouble("start"),x.getDouble("end"),x.getString("text")));}
  byte[] bytes=readBytes(pcm);FloatBuffer fb=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();float[] audio=new float[fb.remaining()];fb.get(audio);
  List<ClipLogic.Moment> selected=ClipLogic.select(phrases,audio,16000,duration,length,args.optBoolean("strict",false));pcm.delete();
  for(ClipLogic.Moment m:selected){if(created()>=maxClips)break;check();double a=origin+m.start,b=origin+m.end;if(duplicate(a,b))continue;renderClip(source,m,phrases,origin);}
  synchronized(LOCK){state.put("scannedSeconds",origin+duration);persist();}
  if(selected.isEmpty())phase("waiting","В этом фрагменте выраженных кандидатов не найдено. Продолжаю анализ.");
 }
 private boolean duplicate(double s,double e)throws Exception{synchronized(LOCK){JSONArray clips=state.getJSONArray("clips");for(int i=0;i<clips.length();i++){JSONObject c=clips.getJSONObject(i);if(sourceKey.equals(c.optString("sourceKey"))&&ClipLogic.overlaps(s,e,c.optDouble("start"),c.optDouble("end")))return true;}return false;}}
 private void renderClip(File source,ClipLogic.Moment moment,List<ClipLogic.Phrase> phrases,double origin)throws Exception{
  phase("rendering","Собираю вертикальный MP4 с субтитрами");String id=UUID.randomUUID().toString();File out=new File(output,id+".mp4"),ass=new File(work,"captions.ass");writeAss(ass,phrases,moment.start,moment.end);
  String filter;
  if(args.optString("layout","portrait").equals("split")){double x=args.optDouble("cameraX"),y=args.optDouble("cameraY"),w=args.optDouble("cameraW"),h=args.optDouble("cameraH");filter=String.format(Locale.US,"[0:v]split=2[cam][game];[cam]crop=iw*%.4f:ih*%.4f:iw*%.4f:ih*%.4f,scale=720:400:force_original_aspect_ratio=increase,crop=720:400[c];[game]scale=720:880:force_original_aspect_ratio=decrease,pad=720:880:(ow-iw)/2:(oh-ih)/2:black[g];[c][g]vstack=inputs=2,setsar=1,subtitles='%s':fontsdir='/system/fonts'[v]",w,h,x,y,ass.getAbsolutePath());}
  else{double focus=Math.max(0,Math.min(1,args.optDouble("focus",.5)));filter=String.format(Locale.US,"[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280:(iw-720)*%.4f:(ih-1280)/2,setsar=1,subtitles='%s':fontsdir='/system/fonts'[v]",focus,ass.getAbsolutePath());}
  List<String> cmd=new ArrayList<>(Arrays.asList("-y","-ss",String.valueOf(moment.start),"-i",source.getAbsolutePath(),"-t",String.valueOf(moment.end-moment.start),"-filter_complex",filter,"-map","[v]","-map","0:a:0?","-c:v","libx264","-preset","ultrafast","-crf","23","-r","25","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-movflags","+faststart",out.getAbsolutePath()));
  try{ff(cmd);}catch(Exception e){out.delete();throw e;}if(out.length()<1024)throw new IOException("Экспорт не создал видео");
  String title="Момент "+(created()+1);for(ClipLogic.Phrase p:phrases)if(ClipLogic.overlaps(p.start,p.end,moment.start,moment.end)){title=p.text.trim();break;}if(title.length()>90)title=title.substring(0,90);
  JSONObject clip=new JSONObject().put("id",id).put("title",title).put("path",out.getAbsolutePath()).put("sourceKey",sourceKey).put("start",origin+moment.start).put("end",origin+moment.end).put("reason",moment.reason).put("bytes",out.length()).put("createdAt",System.currentTimeMillis());
  synchronized(LOCK){state.getJSONArray("clips").put(clip);state.put("jobCreated",created()+1);persist();}
 }
 private void writeAss(File file,List<ClipLogic.Phrase> phrases,double start,double end)throws Exception{
  StringBuilder s=new StringBuilder("[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Main,Arial,48,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,45,45,230,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n");
  for(ClipLogic.Phrase p:phrases){double a=Math.max(start,p.start),b=Math.min(end,p.end);if(b<=a)continue;String text=p.text.trim().replace("\\"," ").replace("{","(").replace("}",")").replace("\n"," ");String[] words=text.split("\\s+");int groups=Math.max(1,(int)Math.ceil(words.length/5.));for(int g=0;g<groups;g++){int from=g*5,to=Math.min(words.length,from+5);String line=String.join(" ",Arrays.copyOfRange(words,from,to));double gs=a+(b-a)*g/groups,ge=a+(b-a)*(g+1)/groups;s.append("Dialogue: 0,").append(assTime(gs-start)).append(',').append(assTime(ge-start)).append(",Main,,0,0,0,,{\\fad(60,60)\\fscx95\\fscy95\\t(0,100,\\fscx100\\fscy100)}").append(line).append('\n');}}
  try(FileOutputStream stream=new FileOutputStream(file)){stream.write(s.toString().getBytes(StandardCharsets.UTF_8));}
 }
 private String assTime(double t){int cs=(int)Math.round(Math.max(0,t)*100);return String.format(Locale.US,"%d:%02d:%02d.%02d",cs/360000,cs/6000%60,cs/100%60,cs%100);}
 private Process startFF(List<String> options)throws Exception{
  File bin=new File(getApplicationInfo().nativeLibraryDir,"libffmpeg.so");if(!bin.isFile())throw new IOException("В APK отсутствует FFmpeg");List<String> cmd=new ArrayList<>();cmd.add(bin.getAbsolutePath());cmd.add("-hide_banner");cmd.add("-loglevel");cmd.add("error");cmd.addAll(options);ProcessBuilder builder=new ProcessBuilder(cmd).redirectErrorStream(true);
  File packages=new File(getNoBackupFilesDir(),"youtubedl-android/packages");builder.environment().put("LD_LIBRARY_PATH",new File(packages,"ffmpeg/usr/lib").getAbsolutePath()+":"+new File(packages,"python/usr/lib").getAbsolutePath());builder.environment().put("SSL_CERT_FILE",new File(packages,"python/usr/etc/tls/cert.pem").getAbsolutePath());return builder.start();
 }
 private String ff(List<String> options)throws Exception{check();Process p=startFF(options);Process old=ffProcess;ffProcess=p;StringBuilder log=new StringBuilder();try(BufferedReader r=new BufferedReader(new InputStreamReader(p.getInputStream()))){String line;while((line=r.readLine())!=null){log.append(line).append('\n');if(log.length()>16000)log.delete(0,8000);if(stopping){p.destroy();throw new InterruptedException();}}}int code=p.waitFor();ffProcess=old;if(code!=0)throw new IOException("FFmpeg: "+log);return log.toString();}
 private double seconds(File f)throws Exception{Process p=startFF(Arrays.asList("-loglevel","info","-i",f.getAbsolutePath(),"-an"));StringBuilder log=new StringBuilder();try(BufferedReader r=new BufferedReader(new InputStreamReader(p.getInputStream()))){String l;while((l=r.readLine())!=null){log.append(l).append('\n');if(stopping){p.destroy();throw new InterruptedException();}}}p.waitFor();java.util.regex.Matcher m=java.util.regex.Pattern.compile("Duration: (\\d+):(\\d+):(\\d+\\.\\d+)").matcher(log);if(!m.find())throw new IOException("Неизвестная длительность фрагмента");return Integer.parseInt(m.group(1))*3600+Integer.parseInt(m.group(2))*60+Double.parseDouble(m.group(3));}
 private void downloadModel()throws Exception{phase("model","Загрузка модели речи (~75 МБ). Обработка будет на телефоне.");File temp=new File(model.getParentFile(),"tiny.part");HttpURLConnection c=(HttpURLConnection)new URL("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin").openConnection();c.setConnectTimeout(20000);c.setReadTimeout(30000);try{if(c.getResponseCode()!=200)throw new IOException("Не удалось загрузить модель: HTTP "+c.getResponseCode());try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(temp)){byte[] buf=new byte[65536];int n;long total=0;while((n=in.read(buf))!=-1){check();out.write(buf,0,n);total+=n;if(total>100*1024*1024)throw new IOException("Неожиданный размер модели");}}if(temp.length()<50*1024*1024)throw new IOException("Модель загрузилась не полностью");try(DataInputStream in=new DataInputStream(new FileInputStream(temp))){if(Integer.reverseBytes(in.readInt())!=0x67676d6c)throw new IOException("Неверный формат модели Whisper");}if(!temp.renameTo(model))throw new IOException("Не удалось сохранить модель");}finally{c.disconnect();temp.delete();}}
 private void sleep(long ms)throws Exception{for(long n=0;n<ms&&!stopping;n+=500)Thread.sleep(500);if(stopping)throw new InterruptedException();}
 private static JSONObject readJSON(File f){try{return new JSONObject(new String(readBytes(f),StandardCharsets.UTF_8));}catch(Exception e){return new JSONObject();}}
 private static byte[] readBytes(File f)throws IOException{try(InputStream in=new FileInputStream(f);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buf=new byte[65536];int n;while((n=in.read(buf))!=-1)out.write(buf,0,n);return out.toByteArray();}}
 private static void writeJSON(File f,JSONObject data)throws IOException{File temp=new File(f.getParentFile(),f.getName()+".part");try(OutputStream out=new FileOutputStream(temp)){out.write(data.toString().getBytes(StandardCharsets.UTF_8));}if(!temp.renameTo(f))throw new IOException("Не удалось сохранить прогресс");}
 private static void deleteTree(File f){if(f.isDirectory()){File[] children=f.listFiles();if(children!=null)for(File c:children)deleteTree(c);}f.delete();}
 @Override public void onTimeout(int startId,int fgsType){requestStop();phase("interrupted","Android ограничил время фоновой обработки. Готовые клипы сохранены.");stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();}
 @Override public void onDestroy(){if(active==this)requestStop();super.onDestroy();}
}
