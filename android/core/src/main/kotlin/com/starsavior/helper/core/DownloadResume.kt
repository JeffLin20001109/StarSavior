package com.starsavior.helper.core

/**
 * 下載中斷後續傳（HTTP Range）的判斷，給 App 內更新下載 APK 用。
 */
object DownloadResume {
    /** 要從哪個位置繼續下載：伺服器回 206 且起點相符才續傳，否則（200 等）從頭開始。 */
    fun resumeFrom(requested: Long, status: Int, contentRange: String?): Long {
        if (requested <= 0 || status != 206) return 0
        val start = Regex("""bytes\s+(\d+)-""").find(contentRange ?: "")?.groupValues?.get(1)?.toLongOrNull()
        return if (start == requested) requested else 0
    }

    /** 檔案總大小：206 時從 Content-Range 的「/總大小」取得，200 時用 Content-Length；不知道時回傳 -1。 */
    fun totalSize(status: Int, contentRange: String?, contentLength: Long): Long {
        if (status == 206) {
            val total = Regex("""/(\d+)\s*$""").find(contentRange ?: "")?.groupValues?.get(1)?.toLongOrNull()
            if (total != null) return total
        }
        return if (contentLength >= 0) contentLength else -1
    }

    /** 第 attempt 次重試前要等多久（毫秒）：2、4、8… 秒，最多 15 秒。 */
    fun backoffMs(attempt: Int): Long = minOf(15_000L, 2_000L shl (attempt - 1).coerceIn(0, 4))
}
