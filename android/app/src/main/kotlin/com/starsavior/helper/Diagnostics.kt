package com.starsavior.helper

import android.app.ActivityManager
import android.app.Application
import android.app.ApplicationExitInfo
import android.content.Context
import android.os.Build
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 啟動時記錄未處理的例外，方便找出「自動關閉」的原因。 */
class HelperApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                val trace = StringWriter().also { error.printStackTrace(PrintWriter(it)) }.toString()
                Diagnostics.log(this, "程式當機：${error.javaClass.simpleName}: ${error.message}")
                File(filesDir, Diagnostics.CRASH_FILE).writeText(Diagnostics.now() + "\n" + trace)
            }
            previous?.uncaughtException(thread, error)
        }
    }
}

/** 事件紀錄（啟動、擷取被停止、結束等），在主畫面顯示最近幾筆。 */
object Diagnostics {
    const val CRASH_FILE = "last_crash.txt"
    private const val LOG_FILE = "events.log"
    private const val MAX_LINES = 40

    fun now(): String = SimpleDateFormat("MM-dd HH:mm:ss", Locale.TAIWAN).format(Date())

    @Synchronized
    fun log(context: Context, message: String) {
        runCatching {
            val file = File(context.filesDir, LOG_FILE)
            val lines = (if (file.exists()) file.readLines() else emptyList()) + "${now()}  $message"
            file.writeText(lines.takeLast(MAX_LINES).joinToString("\n"))
        }
    }

    fun recentEvents(context: Context, count: Int = 8): List<String> =
        File(context.filesDir, LOG_FILE).takeIf { it.exists() }?.readLines()?.takeLast(count) ?: emptyList()

    fun lastCrash(context: Context): String? =
        File(context.filesDir, CRASH_FILE).takeIf { it.exists() }?.readText()?.lines()?.take(12)?.joinToString("\n")

    /** 系統記錄的上次結束原因（Android 11 以上）。 */
    fun lastExitReason(context: Context): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = am.getHistoricalProcessExitReasons(context.packageName, 0, 1).firstOrNull() ?: return null
        val reason = when (info.reason) {
            ApplicationExitInfo.REASON_CRASH, ApplicationExitInfo.REASON_CRASH_NATIVE -> "程式當機"
            ApplicationExitInfo.REASON_ANR -> "程式沒有回應（ANR）"
            ApplicationExitInfo.REASON_LOW_MEMORY -> "手機記憶體不足，被系統關閉"
            ApplicationExitInfo.REASON_USER_REQUESTED -> "被強制停止（設定或清除最近使用的 App）"
            ApplicationExitInfo.REASON_USER_STOPPED -> "被使用者停止"
            ApplicationExitInfo.REASON_EXIT_SELF -> "程式自行結束"
            ApplicationExitInfo.REASON_SIGNALED -> "被系統終止（多半是省電或背景限制）"
            ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "耗用資源過多，被系統關閉"
            ApplicationExitInfo.REASON_PERMISSION_CHANGE -> "權限變更"
            ApplicationExitInfo.REASON_DEPENDENCY_DIED -> "相依的系統元件結束"
            else -> "其他（代碼 ${info.reason}）"
        }
        val time = SimpleDateFormat("MM-dd HH:mm", Locale.TAIWAN).format(Date(info.timestamp))
        return "$time  $reason" + (info.description?.takeIf { it.isNotBlank() }?.let { "：$it" } ?: "")
    }
}
