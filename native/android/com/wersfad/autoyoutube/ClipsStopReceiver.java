package com.wersfad.autoyoutube;
import android.content.*;
public final class ClipsStopReceiver extends BroadcastReceiver { @Override public void onReceive(Context c,Intent i){ClipsService.requestStop();} }
