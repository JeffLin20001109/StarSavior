package com.starsavior.helper.core

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * 檢查程式本身有沒有新版本（對應 Windows 版 update.py）。
 *
 * 正式版 APK（GitHub Actions、main 分支）打包時會把 commit 寫進 BuildConfig.BUILD_COMMIT；
 * release「android-latest」同時放一份 version.json：
 *   {"commit": "...", "url": "arm64 APK 網址", "urls": {"arm64-v8a": "...", "x86_64": "..."}}
 * url 給只認得這個欄位的舊版 App；urls 依 ABI 列出，依裝置支援的 ABI 挑選。
 */
object UpdateCheck {
    data class Update(val commit: String, val url: String)

    /**
     * 回傳新版本資訊；目前版本沒有 commit、內容格式不對或已是最新版時回傳 null。
     * abis：裝置支援的 ABI（Build.SUPPORTED_ABIS，偏好的在前）。
     */
    fun newer(current: String?, payload: String, abis: List<String> = emptyList()): Update? {
        if (current.isNullOrEmpty()) return null
        val info = runCatching { parseJson(payload) }.getOrNull() as? JsonObject ?: return null
        val latest = info.string("commit")
        if (latest.isNullOrEmpty() || latest == current) return null
        val urls = info["urls"] as? JsonObject
        val byAbi = abis.firstNotNullOfOrNull { abi -> urls?.string(abi)?.takeIf { it.isNotEmpty() } }
        return Update(latest, byAbi ?: info.string("url") ?: "")
    }

    private fun JsonObject.string(key: String): String? =
        (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content
}
