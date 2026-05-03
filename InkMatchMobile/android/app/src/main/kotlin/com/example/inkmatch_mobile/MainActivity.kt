package com.example.inkmatch_mobile

import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import com.yandex.mapkit.MapKitFactory

class MainActivity : FlutterActivity() {
    private val configChannel = "inkmatch/config"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        MapKitFactory.initialize(this)
    }

    override fun onStart() {
        super.onStart()
        MapKitFactory.getInstance().onStart()
    }

    override fun onStop() {
        MapKitFactory.getInstance().onStop()
        super.onStop()
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, configChannel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getApiBaseUrl" -> result.success(BuildConfig.INKMATCH_API_BASE_URL)
                    else -> result.notImplemented()
                }
            }
    }
}
