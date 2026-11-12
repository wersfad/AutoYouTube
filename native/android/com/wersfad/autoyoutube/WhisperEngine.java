package com.wersfad.autoyoutube;
public final class WhisperEngine {
 static{System.loadLibrary("aytwhisper");}
 public static native String decode(String model,String pcm,int threads,String language);
 public static native void cancel();
 private WhisperEngine(){}
}
