package com.starsavior.helper.core

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * 檢查程式本身有沒有新版本（對應 Windows 版 update.py）。
 *
 * 正式版 APK（GitHub Actions、main 分支）打包時會把 commit 寫進 BuildConfig.BUILD_COMMIT；
 * release「android-latest」同時放一份 version.json：{"commit": "...", "url": "APK 下載網址"}。
 */
object UpdateCheck {
    data class Update(val commit: String, val url: String)

    /** 回傳新版本資訊；目前版本沒有 commit、內容格式不對或已是最新版時回傳 null。 */
    fun newer(current: String?, payload: String): Update? {
        if (current.isNullOrEmpty()) return null
        val info = runCatching { parseJson(payload) }.getOrNull() as? JsonObject ?: return null
        val latest = (info["commit"] as? JsonPrimitive)?.takeIf { it.isString }?.content
        if (latest.isNullOrEmpty() || latest == current) return null
        val url = (info["url"] as? JsonPrimitive)?.takeIf { it.isString }?.content ?: ""
        return Update(latest, url)
    }
}
