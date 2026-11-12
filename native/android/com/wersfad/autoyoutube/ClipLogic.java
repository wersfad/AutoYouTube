package com.wersfad.autoyoutube;
import java.util.*;

/** Pure JVM selection/coverage logic. No fake clips and no dependence on an LLM. */
public final class ClipLogic {
 public static final class Phrase {
  public final double start,end; public final String text;
  public Phrase(double s,double e,String t){start=s;end=e;text=t;}
 }
 public static final class Moment {
  public final double start,end,score; public final String reason;
  Moment(double s,double e,double q,String r){start=s;end=e;score=q;reason=r;}
 }
 public static boolean overlaps(double a,double b,double c,double d){return Math.max(a,c)<Math.min(b,d);}
 public static boolean allowedHost(String host){return host!=null&&Arrays.asList("youtube.com","www.youtube.com","m.youtube.com","youtu.be","twitch.tv","www.twitch.tv","m.twitch.tv").contains(host.toLowerCase(Locale.ROOT));}
 public static List<Moment> select(List<Phrase> phrases,float[] audio,int rate,double duration,double length,boolean strict){
  List<Moment> candidates=new ArrayList<>();
  if(duration<Math.min(12,length))return candidates;
  double[] rms=new double[(int)Math.ceil(audio.length/(double)rate)];
  for(int i=0;i<audio.length;i++){double v=audio[i];rms[i/rate]+=v*v/rate;}
  for(int i=0;i<rms.length;i++)rms[i]=Math.sqrt(rms[i]);
  double[] sorted=rms.clone();Arrays.sort(sorted);double base=sorted.length==0?0:sorted[sorted.length/2];
  for(int t=0;t<duration;t+=5){
   double s=Math.max(0,t-8),e=Math.min(duration,s+length);if(e-s<12)continue;
   StringBuilder text=new StringBuilder();int count=0;
   for(Phrase p:phrases)if(overlaps(s,e,p.start,p.end)){text.append(' ').append(p.text);count++;}
   String tx=text.toString().toLowerCase(Locale.ROOT);int hits=0;
   for(String word:new String[]{"не может быть","смотри","смотрите","офигеть","победа","выиграл","последний","смешно","ахах","невероятно","clutch","unbelievable","no way","let's go","victory","insane"})if(tx.contains(word))hits++;
   double peak=0;for(int j=(int)s;j<Math.min(rms.length,(int)Math.ceil(e));j++)peak=Math.max(peak,rms[j]);
   boolean audioPeak=peak>Math.max(.045,base*2.5);double score=Math.min(3,hits)*2+(audioPeak?2:0)+(count>=2?.5:0);
   if(score>=(strict?4:2.5))candidates.add(new Moment(s,e,score,hits>0?"Реакция в речи / эмоциональный звук":"Звуковой пик"));
  }
  candidates.sort((a,b)->Double.compare(b.score,a.score));List<Moment> out=new ArrayList<>();
  for(Moment m:candidates){boolean duplicate=false;for(Moment old:out)if(overlaps(m.start,m.end,old.start,old.end))duplicate=true;if(!duplicate)out.add(m);if(out.size()>=3)break;}
  out.sort(Comparator.comparingDouble(x->x.start));return out;
 }
 private ClipLogic(){}
}
