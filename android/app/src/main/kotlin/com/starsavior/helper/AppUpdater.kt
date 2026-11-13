package com.starsavior.helper

import android.app.Activity
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
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

    /** 下載 APK 到 App 的快取資料夾（跟隨 GitHub 的重新導向）；onProgress 回報 0～100，總大小未知時為 -1。 */
    fun download(activity: Activity, url: String, onProgress: (Int) -> Unit): File {
        val file = File(activity.cacheDir, "update.apk")
        val tmp = File(activity.cacheDir, "update.apk.part")
        var target = URL(url)
        repeat(5) {
            val conn = target.openConnection() as HttpURLConnection
            conn.connectTimeout = 20_000
            conn.readTimeout = 30_000
            conn.instanceFollowRedirects = false
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (StarSaviorJourneyHelper Android)")
            try {
                val code = conn.responseCode
                if (code in 300..399) {
                    target = URL(target, conn.getHeaderField("Location"))
                    return@repeat
                }
                if (code !in 200..299) throw IOException("HTTP $code：$target")
                val total = conn.contentLengthLong
                var done = 0L
                var last = -2
                conn.inputStream.use { input ->
                    tmp.outputStream().use { output ->
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
                if (!tmp.renameTo(file)) { tmp.copyTo(file, overwrite = true); tmp.delete() }
                return file
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
            else -> "安裝失敗：" + (intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "未知原因") +
                "\n可以改用瀏覽器下載 APK 手動安裝。"
        }
    }
}
