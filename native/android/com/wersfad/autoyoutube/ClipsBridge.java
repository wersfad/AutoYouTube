package com.wersfad.autoyoutube;
import android.app.Activity;
import android.content.*;
import android.os.Build;
import io.flutter.embedding.engine.FlutterEngine;
import io.flutter.plugin.common.MethodChannel;
import org.json.*;
import java.io.File;

public final class ClipsBridge {
 public static void attach(Activity activity,FlutterEngine engine){
  new MethodChannel(engine.getDartExecutor().getBinaryMessenger(),"autoyoutube/clips").setMethodCallHandler((call,result)->{
   try{
    JSONObject args=call.arguments==null?new JSONObject():new JSONObject((java.util.Map<?,?>)call.arguments);
    switch(call.method){
     case "clips.status":result.success(ClipsService.snapshot(activity).toString());break;
     case "clips.start":case "clips.model":
      if(call.method.equals("clips.start"))ClipsService.validate(args);
      if(ClipsService.isActive())throw new IllegalStateException("Обработка уже запущена. Сначала остановите её.");
      if(Build.VERSION.SDK_INT>=33&&activity.checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)activity.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},7001);
      Intent intent=new Intent(activity,ClipsService.class).putExtra("command",call.method).putExtra("args",args.toString());
      if(Build.VERSION.SDK_INT>=26)activity.startForegroundService(intent);else activity.startService(intent);
      result.success("{\"accepted\":true}");break;
     case "clips.stop":ClipsService.requestStop();result.success("{\"accepted\":true}");break;
     case "clips.file":
      JSONObject state=ClipsService.snapshot(activity);JSONArray clips=state.optJSONArray("clips");String id=args.optString("id");String path=null;
      if(clips!=null)for(int i=0;i<clips.length();i++){JSONObject c=clips.getJSONObject(i);if(c.optString("id").equals(id))path=c.optString("path");}
      if(path==null)throw new IllegalArgumentException("Клип не найден");
      File f=new File(path);File root=new File(activity.getFilesDir(),"clips/output");
      if(!f.getCanonicalPath().startsWith(root.getCanonicalPath()+File.separator)||!f.isFile())throw new IllegalArgumentException("Файл недоступен");
      result.success(f.getAbsolutePath());break;
     default:result.notImplemented();
    }
   }catch(Exception e){result.error("clips_error",e.getMessage(),null);}
  });
 }
 private ClipsBridge(){}
}
