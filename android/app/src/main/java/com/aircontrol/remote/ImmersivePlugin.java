package com.aircontrol.remote;

import android.app.Activity;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "Immersive")
public class ImmersivePlugin extends Plugin {
    private static volatile boolean enabled;

    @PluginMethod
    public void setEnabled(PluginCall call) {
        Boolean requested = call.getBoolean("enabled");
        if (requested == null) {
            call.reject("enabled is required");
            return;
        }
        enabled = requested;
        Activity activity = getActivity();
        activity.runOnUiThread(() -> {
            apply(activity, enabled);
            call.resolve();
        });
    }

    static boolean isEnabled() {
        return enabled;
    }

    static void apply(Activity activity, boolean fullscreen) {
        WindowCompat.setDecorFitsSystemWindows(activity.getWindow(), !fullscreen);
        WindowInsetsControllerCompat controller = new WindowInsetsControllerCompat(
                activity.getWindow(), activity.getWindow().getDecorView());
        if (fullscreen) {
            controller.hide(androidx.core.view.WindowInsetsCompat.Type.systemBars());
            controller.setSystemBarsBehavior(
                    WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        } else {
            controller.show(androidx.core.view.WindowInsetsCompat.Type.systemBars());
        }
    }
}
