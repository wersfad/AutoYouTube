#!/usr/bin/env python3
"""Adds in-app YouTube sign-in: cookies from a WebView login are passed to yt-dlp."""
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
pkg = root / 'native/android/com/wersfad/autoyoutube'

def patch(path, pairs, marker):
    s = path.read_text(encoding='utf-8')
    if marker in s:
        return
    for old, new in pairs:
        assert old in s, f'{path.name}: anchor not found: {old[:70]}'
        s = s.replace(old, new, 1)
    path.write_text(s, encoding='utf-8')

# 1) Login activity
(pkg / 'YoutubeLoginActivity.java').write_text(r'''package com.wersfad.autoyoutube;
import android.app.Activity;
import android.content.Context;
import android.os.Bundle;
import android.webkit.*;
import android.widget.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** AYT_LOGIN: sign in to YouTube once, cookies are stored only on this phone. */
public final class YoutubeLoginActivity extends Activity {
 private WebView web;
 public static File file(Context c){return new File(c.getFilesDir(),"clips/cookies.txt");}
 public static void clear(Context c){file(c).delete();CookieManager.getInstance().removeAllCookies(null);CookieManager.getInstance().flush();}
 @Override protected void onCreate(Bundle b){
  super.onCreate(b);
  CookieManager cm=CookieManager.getInstance();cm.setAcceptCookie(true);
  LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
  Button done=new Button(this);done.setText("Готово, сохранить вход");done.setOnClickListener(v->finishLogin());
  web=new WebView(this);cm.setAcceptThirdPartyCookies(web,true);
  WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);
  s.setUserAgentString(s.getUserAgentString().replace("; wv","").replaceAll("Version/\\S+ ",""));
  web.setWebViewClient(new WebViewClient(){@Override public void onPageFinished(WebView v,String url){if(url!=null&&url.contains("youtube.com")&&!url.contains("accounts."))autoSave();}});
  root.addView(done,new LinearLayout.LayoutParams(-1,-2));
  root.addView(web,new LinearLayout.LayoutParams(-1,0,1f));
  setContentView(root);
  web.loadUrl("https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fm.youtube.com%2F");
 }
 private void finishLogin(){
  CookieManager cm=CookieManager.getInstance();cm.flush();
  String c=cm.getCookie("https://www.youtube.com");
  if(c==null||!(c.contains("SAPISID=")||c.contains("__Secure-3PSID="))){Toast.makeText(this,"Вход не найден. Войдите в аккаунт Google и дождитесь открытия YouTube.",Toast.LENGTH_LONG).show();return;}
  try{
   long exp=System.currentTimeMillis()/1000+180L*24*3600;
   StringBuilder out=new StringBuilder("# Netscape HTTP Cookie File\n");
   for(String part:c.split(";")){String p=part.trim();int eq=p.indexOf('=');if(eq<=0)continue;
    out.append(".youtube.com\tTRUE\t/\tTRUE\t").append(exp).append('\t').append(p.substring(0,eq)).append('\t').append(p.substring(eq+1)).append('\n');}
   File f=file(this);f.getParentFile().mkdirs();
   try(OutputStream o=new FileOutputStream(f)){o.write(out.toString().getBytes(StandardCharsets.UTF_8));}
   saved=true;Toast.makeText(this,"Вход в YouTube сохранён",Toast.LENGTH_SHORT).show();finish();
  }catch(Exception e){Toast.makeText(this,"Не удалось сохранить вход: "+e.getMessage(),Toast.LENGTH_LONG).show();}
 }
 private boolean saved=false;
 private void autoSave(){if(saved)return;CookieManager cm=CookieManager.getInstance();cm.flush();String c=cm.getCookie("https://www.youtube.com");if(c!=null&&(c.contains("SAPISID=")||c.contains("__Secure-3PSID=")))finishLogin();}
 @Override protected void onPause(){autoSave();super.onPause();}
 @Override public void onBackPressed(){autoSave();if(!saved)super.onBackPressed();}
}
''', encoding='utf-8')

# 2) use cookies in every yt-dlp call (runs after fix_ytdlp.py)
patch(pkg / 'ClipsService.java', [
 ('r.addOption("--extractor-args","youtube:player_client=android_vr,tv_simply,web_safari,default");',
  '/*AYT_LOGIN*/File ck=YoutubeLoginActivity.file(this);if(ck.isFile()){r.addOption("--cookies",ck.getAbsolutePath());r.addOption("--extractor-args","youtube:player_client=tv,web_safari,mweb");}else r.addOption("--extractor-args","youtube:player_client=android_vr,tv_simply,web_safari,default");'),
 ('state.put("modelReady",', 'state.put("cookiesReady",YoutubeLoginActivity.file(c).isFile());state.put("modelReady",'),
], 'AYT_LOGIN')

# 3) bridge methods
patch(pkg / 'ClipsBridge.java', [
 ('case "clips.stop":',
  '/*AYT_LOGIN*/case "clips.login":activity.startActivity(new Intent(activity,YoutubeLoginActivity.class));result.success("{\\"accepted\\":true}");break;\n'
  '     case "clips.logout":YoutubeLoginActivity.clear(activity);result.success("{\\"accepted\\":true}");break;\n     case "clips.stop":'),
], 'AYT_LOGIN')

# 4) UI
patch(root / 'assets/clips.js', [
 ('<div id="clip-status" aria-live="polite"></div>',
  '<section class="glass card clip-model"><div><h3>Вход в YouTube</h3><p id="clip-login-label">Нужен, если YouTube просит подтвердить, что вы не бот</p></div><button type="button" class="btn ghost sm" id="clip-login-button" onclick="clipsLogin()">Войти</button></section>\n <div id="clip-status" aria-live="polite"></div>'),
 ("state=await native('clips.status');paint();", "state=await native('clips.status');paint();paintLogin();"),
 ('window.clipsShare=',
  "/*AYT_LOGIN*/function paintLogin(){const l=document.getElementById('clip-login-label'),b=document.getElementById('clip-login-button');if(!l||!b)return;b.disabled=active();if(state.cookiesReady){l.textContent='Вход выполнен · видео скачивается от вашего аккаунта';b.textContent='Выйти';b.onclick=window.clipsLogout;}else{l.textContent='Нужен, если YouTube просит подтвердить, что вы не бот';b.textContent='Войти';b.onclick=window.clipsLogin;}}\n"
  "window.clipsLogin=async function(){try{await native('clips.login');toast('Войдите в аккаунт, затем нажмите «Готово» сверху');}catch(err){toast(err.message);}};\n"
  "window.clipsLogout=async function(){try{await native('clips.logout');toast('Вход удалён');refresh();}catch(err){toast(err.message);}};\n"
  "window.clipsShare="),
], 'AYT_LOGIN')

# 5) manifest (after flutter create)
man = root / 'android/app/src/main/AndroidManifest.xml'
s = man.read_text(encoding='utf-8')
if 'YoutubeLoginActivity' not in s:
    assert '</application>' in s
    s = s.replace('</application>', '    <activity android:name=".YoutubeLoginActivity" android:exported="false" android:theme="@android:style/Theme.Material.NoActionBar"/>\n    </application>', 1)
    man.write_text(s, encoding='utf-8')
print('YouTube login added')
