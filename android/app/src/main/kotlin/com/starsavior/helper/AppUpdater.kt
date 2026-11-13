package com.starsavior.helper

import android.app.Activity
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import com.starsavior.helper.core.DownloadResume
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * App 內更新：下載新版 APK，交給系統的 PackageInstaller 安裝。
 *
 * Android 規定側載的 App 不能靜默更新：第一次要允許「安裝未知應用程式」，每次安裝都會跳出系統確認畫面。
 * 安裝結果會以 [ACTION_INSTALL_STATUS] 送回 MainActivity（見 [handleStatus]）。
 */
object AppUpdater {
    const val ACTION_INSTALL_STATUS = "com.starsavior.helper.INSTALL_STATUS"

    /** 是否已允許本 App 安裝 APK；沒有的話開啟設定頁並回傳 false。 */
    fun ensureInstallAllowed(activity: Activity): Boolean {
        if (activity.packageManager.canRequestPackageInstalls()) return true
        activity.startActivity(
            Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}"))
        )
        return false
    }

    private const val MAX_ATTEMPTS = 6

    /**
     * 下載 APK 到 App 的快取資料夾（跟隨 GitHub 的重新導向）。
     * 連線中斷或逾時會自動重試，並從已下載的位置續傳（HTTP Range）。
     * onProgress 回報 0～100（總大小未知時為 -1）；onRetry 回報第幾次重試與原因。
     */
    fun download(
        activity: Activity, url: String,
        onProgress: (Int) -> Unit, onRetry: (Int, String) -> Unit = { _, _ -> },
    ): File {
        val file = File(activity.cacheDir, "update.apk")
        val tmp = File(activity.cacheDir, "update.apk.part")
        tmp.delete()  // 每次按下都重新開始，避免接上舊版本下載到一半的檔案
        var attempt = 0
        while (true) {
            try {
                downloadOnce(url, tmp, onProgress)
                file.delete()
                if (!tmp.renameTo(file)) { tmp.copyTo(file, overwrite = true); tmp.delete() }
                return file
            } catch (e: IOException) {
                attempt++
                if (attempt >= MAX_ATTEMPTS) throw IOException("已重試 ${attempt - 1} 次仍失敗：${e.message}", e)
                onRetry(attempt, e.message ?: e.javaClass.simpleName)
                Thread.sleep(DownloadResume.backoffMs(attempt))
            }
        }
    }

    /** 下載一次：tmp 已有內容時從該位置續傳；伺服器不支援續傳就從頭下載。 */
    private fun downloadOnce(url: String, tmp: File, onProgress: (Int) -> Unit) {
        var target = URL(url)
        repeat(5) {
            val requested = if (tmp.exists()) tmp.length() else 0L
            val conn = target.openConnection() as HttpURLConnection
            conn.connectTimeout = 20_000
            conn.readTimeout = 60_000
            conn.instanceFollowRedirects = false
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (StarSaviorJourneyHelper Android)")
            if (requested > 0) conn.setRequestProperty("Range", "bytes=$requested-")
            try {
                val code = conn.responseCode
                if (code in 300..399) {
                    target = URL(target, conn.getHeaderField("Location"))
                    return@repeat
                }
                if (code == 416) { tmp.delete(); throw IOException("續傳位置無效，重新下載") }
                if (code !in 200..299) throw IOException("HTTP $code")
                val range = conn.getHeaderField("Content-Range")
                val start = DownloadResume.resumeFrom(requested, code, range)
                val total = DownloadResume.totalSize(code, range, conn.contentLengthLong + start)
                var done = start
                var last = -2
                conn.inputStream.use { input ->
                    java.io.FileOutputStream(tmp, start > 0).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val n = input.read(buffer)
                            if (n < 0) break
                            output.write(buffer, 0, n)
                            done += n
                            val percent = if (total > 0) (done * 100 / total).toInt() else -1
                            if (percent != last) { last = percent; onProgress(percent) }
                        }
                    }
                }
                if (total > 0 && done != total) throw IOException("下載不完整（$done / $total）")
                return
            } finally {
                conn.disconnect()
            }
        }
        throw IOException("重新導向次數過多：$url")
    }

    /** 把 APK 寫進 PackageInstaller 的安裝工作並送出；系統會再要求使用者確認。 */
    fun install(activity: Activity, apk: File) {
        val installer = activity.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(activity.packageName)
        val sessionId = installer.createSession(params)
        installer.openSession(sessionId).use { session ->
            session.openWrite("StarSaviorJourneyHelper.apk", 0, apk.length()).use { out ->
                apk.inputStream().use { it.copyTo(out) }
                session.fsync(out)
            }
            val intent = Intent(activity, MainActivity::class.java).setAction(ACTION_INSTALL_STATUS)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val pending = PendingIntent.getActivity(activity, sessionId, intent, flags)
            session.commit(pending.intentSender)
        }
    }

    /**
     * 處理安裝結果。回傳要顯示的訊息；需要使用者確認時會開啟系統的安裝畫面並回傳 null。
     */
    fun handleStatus(activity: Activity, intent: Intent): String? {
        return when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (confirm != null) activity.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                null
            }
            PackageInstaller.STATUS_SUCCESS -> "更新完成。"
            PackageInstaller.STATUS_FAILURE_ABORTED -> "已取消安裝。可以再按一次「下載並安裝」。"
            else -> {
                val detail = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "未知原因"
                if (detail.contains("signatures do not match", ignoreCase = true) ||
                    detail.contains("UPDATE_INCOMPATIBLE", ignoreCase = true)) {
                    "新版的簽章和目前安裝的不同，無法直接覆蓋（舊版 APK 的簽章金鑰不固定）。\n" +
                        "請先解除安裝旅程助手，再按「改用瀏覽器下載」安裝新版；之後的更新就能直接覆蓋。"
                } else {
                    "安裝失敗：$detail\n可以改用瀏覽器下載 APK 手動安裝。"
                }
            }
        }
    }
}
