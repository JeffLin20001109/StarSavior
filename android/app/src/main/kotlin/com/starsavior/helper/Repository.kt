package com.starsavior.helper

import android.content.Context
import android.util.Log
import com.starsavior.helper.core.GameData
import com.starsavior.helper.core.TableTranslator
import com.starsavior.helper.core.parseJson
import kotlinx.serialization.json.jsonObject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * 網站資料、譯文表、卡圖的下載與本機快取（對應 Windows 版 data.py、translations.py、translate.py）。
 * 與 Windows 版使用同一份網站 JSON 與同一份線上譯文表。
 */
class Repository(private val context: Context) {
    @Volatile var data: GameData? = null
        private set
    @Volatile var status: String = "正在下載旅程資料…"
        private set
    @Volatile var translationStatus: String = ""
        private set

    val translator: TableTranslator = TableTranslator(loadBundledAndCachedTable(), fallback = { googleTranslate(it) })

    private val siteDir = File(context.filesDir, "site").apply { mkdirs() }
    private val translationCache = File(context.filesDir, "translations_zh.json")
    val cardDir = File(context.cacheDir, "cards").apply { mkdirs() }

    /** 背景持續確保資料可用：失敗時 5 秒起倍增、最長每 60 秒重試；成功後每 12 小時更新。 */
    fun start(scope: CoroutineScope, onDataReady: () -> Unit) {
        scope.launch(Dispatchers.IO) {
            var wait = 5_000L
            var attempt = 0
            while (isActive) {
                attempt++
                refreshTranslations()
                val fresh = try {
                    val first = data == null
                    data = loadSiteData()
                    status = "旅程資料：${data!!.journeyCount()} 個旅程事件、${data!!.cards.size} 張阿爾克那"
                    if (first) onDataReady()
                    true
                } catch (e: Exception) {
                    Log.w(TAG, "網站資料下載失敗", e)
                    status = if (data == null) "下載失敗，${wait / 1000} 秒後自動重試（已試 $attempt 次）：${e.message}"
                    else "無法連線，使用本機資料（${e.message}）"
                    false
                }
                if (fresh) {
                    wait = 5_000L
                    attempt = 0
                    delay(DATA_MAX_AGE_MS)
                } else {
                    delay(wait)
                    wait = minOf(wait * 2, 60_000L)
                }
            }
        }
    }

    /** 下載我們自己的資料庫（journey_data.json）；失敗時使用本機快取。 */
    private fun loadSiteData(): GameData {
        val cache = File(siteDir, "journey_data.json")
        val fresh = cache.exists() && System.currentTimeMillis() - cache.lastModified() < DATA_MAX_AGE_MS
        if (!fresh) {
            try {
                val text = httpGet(DATA_URL)
                val parsed = GameData(parseJson(text).jsonObject)  // 能解析才寫入快取
                cache.writeText(text)
                return parsed
            } catch (e: Exception) {
                if (!cache.exists()) throw e
                Log.w(TAG, "下載旅程資料失敗，使用快取", e)
            }
        }
        return GameData(parseJson(cache.readText()).jsonObject)
    }

    private fun loadBundledAndCachedTable(): Map<String, String> {
        val table = LinkedHashMap<String, String>()
        try {
            context.assets.open("translations_zh.json").bufferedReader().use { table.putAll(TableTranslator.parseTable(it.readText())) }
        } catch (e: Exception) {
            Log.w(TAG, "無法讀取內建譯文表", e)
        }
        val cache = File(context.filesDir, "translations_zh.json")
        if (cache.exists()) runCatching { table.putAll(TableTranslator.parseTable(cache.readText())) }
        translationStatus = "譯文表：${table.size} 句"
        return table
    }

    /** 下載最新譯文表（每 6 小時）；失敗時保留現有內容。 */
    private fun refreshTranslations() {
        if (translationCache.exists() && System.currentTimeMillis() - translationCache.lastModified() < TRANSLATION_MAX_AGE_MS) return
        try {
            val text = httpGet(TRANSLATIONS_URL)
            val table = TableTranslator.parseTable(text)
            require(table.isNotEmpty()) { "譯文表是空的" }
            val untranslated = table.values.count { v -> v.any { it in '가'..'힣' } }
            require(untranslated <= table.size * 0.2) { "譯文表含有大量未翻譯的韓文" }
            translationCache.writeText(text)
            translator.table = translator.table + table
            translationStatus = "譯文表已更新：${translator.table.size} 句"
        } catch (e: Exception) {
            Log.w(TAG, "下載譯文表失敗", e)
            translationStatus = "譯文表使用本機版本（${translator.table.size} 句）"
        }
    }

    /** 卡圖：優先用資料內的圖片欄位，否則依網站規則用韓文卡名組成網址；下載後快取在本機。 */
    fun cardImage(card: kotlinx.serialization.json.JsonObject): ByteArray {
        val url = cardImageUrl(card)
        val file = File(cardDir, "${(card["id"] as? JsonPrimitive)?.content}-${url.hashCode().toUInt()}.img")
        if (file.exists() && file.length() > 0) return file.readBytes()
        val bytes = httpBytes(url)
        file.writeBytes(bytes)
        return bytes
    }

    companion object {
        private const val TAG = "Repository"
        /** 卡圖網址的基準（資料裡沒有圖片網址的舊卡片才會用到）。 */
        const val SITE = "https://star-savior-arcana-db.pages.dev"
        /** 我們自己的資料庫：每天由 GitHub Actions 合併各來源產生。 */
        const val DATA_URL = "https://github.com/JeffLin20001109/StarSavior/releases/download/data/journey_data.json"
        const val TRANSLATIONS_URL = "https://github.com/JeffLin20001109/StarSavior/releases/download/translations/translations_zh.json"
        private const val DATA_MAX_AGE_MS = 12 * 3600_000L
        private const val TRANSLATION_MAX_AGE_MS = 6 * 3600_000L

        fun cardImageUrl(card: kotlinx.serialization.json.JsonObject): String {
            for (key in listOf("image", "img", "image_url", "imageUrl", "thumbnail", "icon")) {
                val value = (card[key] as? JsonPrimitive)?.takeIf { it.isString }?.content?.trim()
                if (!value.isNullOrEmpty()) return URL(URL("$SITE/"), value).toString()
            }
            val name = card["name"]
            val ko = ((name as? kotlinx.serialization.json.JsonObject)?.get("ko-KR") as? JsonPrimitive)?.content ?: ""
            val fileName = ko.replace(Regex("[\\\\/:*?\"<>|\\s]"), "")
            require(fileName.isNotEmpty()) { "卡片沒有名稱，無法取得卡圖" }
            return "$SITE/images/cards/" + URLEncoder.encode(fileName, "UTF-8").replace("+", "%20") + ".webp"
        }

        fun httpBytes(url: String, timeoutMs: Int = 20_000): ByteArray {
            var target = URL(url)
            repeat(5) {  // 跟隨重新導向（GitHub 下載會轉到其他網域）
                val conn = target.openConnection() as HttpURLConnection
                conn.connectTimeout = timeoutMs
                conn.readTimeout = timeoutMs
                conn.instanceFollowRedirects = false
                conn.setRequestProperty("User-Agent", "Mozilla/5.0 (StarSaviorJourneyHelper Android)")
                try {
                    val code = conn.responseCode
                    if (code in 300..399) {
                        target = URL(target, conn.getHeaderField("Location"))
                        return@repeat
                    }
                    if (code !in 200..299) throw java.io.IOException("HTTP $code：$target")
                    return conn.inputStream.use { it.readBytes() }
                } finally {
                    conn.disconnect()
                }
            }
            throw java.io.IOException("重新導向次數過多：$url")
        }

        fun httpGet(url: String): String = String(httpBytes(url), Charsets.UTF_8)

        /** 譯文表沒有的句子才用 Google 翻譯暫時補上。 */
        fun googleTranslate(text: String): String {
            val q = URLEncoder.encode(text, "UTF-8")
            val body = httpGet("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=ko&tl=zh-TW&q=$q")
            val parts = (parseJson(body) as? JsonArray)?.getOrNull(0) as? JsonArray ?: return ""
            return parts.joinToString("") { ((it as? JsonArray)?.getOrNull(0) as? JsonPrimitive)?.content ?: "" }
        }
    }
}
