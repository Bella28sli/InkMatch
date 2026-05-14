package com.example.inkmatch_mobile

import android.app.Application
import android.content.pm.PackageManager
import android.os.Bundle
import com.yandex.mapkit.MapKitFactory

class MainApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        MapKitFactory.setLocale("ru_RU")
        val apiKey = resolveYandexMapkitApiKey()
        if (apiKey.isNotBlank()) {
            MapKitFactory.setApiKey(apiKey)
        }
    }

    private fun resolveYandexMapkitApiKey(): String {
        val buildConfigKey = BuildConfig.YANDEX_MAPKIT_API_KEY.trim()
        if (buildConfigKey.isNotEmpty()) {
            return buildConfigKey
        }

        val appInfo = packageManager.getApplicationInfo(
            packageName,
            PackageManager.GET_META_DATA,
        )
        val metaData: Bundle? = appInfo.metaData
        return metaData?.getString("com.yandex.mapkit.API_KEY")?.trim().orEmpty()
    }
}
