package com.starsavior.helper

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import android.view.WindowManager
import android.widget.Toast
import com.starsavior.helper.core.EventDetector
import com.starsavior.helper.core.Line
import com.starsavior.helper.core.Pipeline
import com.starsavior.helper.core.Renderer
import com.starsavior.helper.core.Result
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 前景服務：顯示懸浮按鈕、擷取螢幕、辨識並顯示結果。
 * 點按鈕：辨識；拖曳：移動；長按按鈕或通知的「結束」：關閉。
 */
class OverlayService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var wm: WindowManager
    private lateinit var repository: Repository
    private lateinit var button: FloatingButton
    private lateinit var popup: ResultPopup
    private var capturer: ScreenCapturer? = null
    private val reader by lazy { TextReader() }
    private val cards by lazy { CardMatcher(repository::cardImage) }
    private var busy = false
    private var pendingFrame: Bitmap? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        repository = Repository(this)
        val prefs = getSharedPreferences("overlay", MODE_PRIVATE)
        button = FloatingButton(this, wm, onTap = ::scan, onLongPress = ::quit) { x, y ->
            prefs.edit().putInt("x", x).putInt("y", y).apply()
        }
        popup = ResultPopup(this, wm)
        val screen = resources.displayMetrics
        button.params.x = prefs.getInt("x", screen.widthPixels - button.sizePx - 24)
        button.params.y = prefs.getInt("y", screen.heightPixels / 3)
        wm.addView(button.view, button.params)
        repository.start(scope) { scope.launch { rerunPending() } }
        Diagnostics.log(this, "旅程助手啟動")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            quit()
            return START_NOT_STICKY
        }
        startForegroundCompat()
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED) ?: Activity.RESULT_CANCELED
        @Suppress("DEPRECATION")
        val data: Intent? = intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        if (capturer == null && resultCode == Activity.RESULT_OK && data != null) {
            val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            val projection = mpm.getMediaProjection(resultCode, data)
            capturer = ScreenCapturer(this, projection, handler) { handler.post { onCaptureStopped() } }
            Diagnostics.log(this, "開始螢幕擷取")
        }
        Toast.makeText(this, "旅程助手已啟動：點「旅」辨識，長按結束", Toast.LENGTH_LONG).show()
        return START_NOT_STICKY
    }

    private fun startForegroundCompat() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "旅程助手", NotificationManager.IMPORTANCE_LOW))
        val stop = PendingIntent.getService(this, 0, Intent(this, OverlayService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_search)
            .setContentTitle("旅程助手執行中")
            .setContentText("點遊戲畫面上的「旅」按鈕辨識事件；長按按鈕結束")
            .addAction(Notification.Action.Builder(null, "結束", stop).build())
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    /** 系統停止了螢幕擷取（例如螢幕關閉、鎖定）：保留按鈕，點一下重新授權。 */
    private fun onCaptureStopped() {
        Diagnostics.log(this, "螢幕擷取被系統停止（按鈕保留，點一下可重新授權）")
        capturer?.release()
        capturer = null
        button.setBusy(false)
        Toast.makeText(this, "螢幕擷取被系統停止了，點「旅」按鈕重新允許即可繼續使用", Toast.LENGTH_LONG).show()
    }

    private fun requestCapture() {
        Diagnostics.log(this, "重新要求螢幕擷取授權")
        startActivity(Intent(this, CaptureActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun scan() {
        if (busy) return
        val capturer = capturer ?: return requestCapture()
        busy = true
        button.setBusy(true)
        // 截圖前先隱藏按鈕與小窗，等下一個畫面
        button.view.visibility = android.view.View.INVISIBLE
        popup.setHiddenForCapture(true)
        scope.launch {
            val started = System.currentTimeMillis()
            val resized = capturer.syncSize()
            delay(if (resized) 400 else 160)
            val frame = capturer.latest()
            button.view.visibility = android.view.View.VISIBLE
            popup.setHiddenForCapture(false)
            val result = if (frame == null) message("無法擷取畫面", "還沒有收到畫面，請再點一次。")
            else withContext(Dispatchers.Default) { recognize(frame) }
            val elapsed = (System.currentTimeMillis() - started) / 100 / 10.0
            busy = false
            button.setBusy(false)
            show(result.copy(lines = result.lines + Line("耗時 $elapsed 秒", "dim")))
        }
    }

    private fun recognize(frame: Bitmap): Result = try {
        val region = EventDetector.scanRegion(frame.width, frame.height)
        val boxes = reader.read(Bitmap.createBitmap(frame, 0, 0, region.width, region.height))
        val pipeline = Pipeline({ repository.data }, { Renderer(it, repository.translator) })
        val result = pipeline.run(boxes, frame.width, frame.height, cards.identifier(frame))
        if (result.title == "資料尚未就緒") {
            // 資料下載完成後自動用這張截圖重新辨識
            pendingFrame = frame
            result.copy(lines = result.lines + Line("狀態：" + repository.status, "dim") +
                Line("資料下載完成後會自動重新辨識這個畫面，不需要再點。", "note"))
        } else result
    } catch (e: Exception) {
        Log.e(TAG, "辨識失敗", e)
        message("發生錯誤", "${e.javaClass.simpleName}: ${e.message}")
    }

    private suspend fun rerunPending() {
        val frame = pendingFrame ?: return
        pendingFrame = null
        show(withContext(Dispatchers.Default) { recognize(frame) })
    }

    private fun show(result: Result) {
        val screen = resources.displayMetrics
        popup.show(result, button.params.x, button.params.y, button.sizePx, screen.widthPixels, screen.heightPixels)
    }

    private fun message(title: String, vararg texts: String) = Result(title, texts.map { Line(it, "warn") })

    private fun quit() {
        Diagnostics.log(this, "使用者結束旅程助手")
        Toast.makeText(this, "旅程助手已結束", Toast.LENGTH_SHORT).show()
        stopSelf()
    }

    override fun onDestroy() {
        Diagnostics.log(this, "服務結束")
        scope.cancel()
        popup.hide()
        runCatching { wm.removeView(button.view) }
        capturer?.release()
        capturer = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "OverlayService"
        private const val CHANNEL = "overlay"
        private const val NOTIFICATION_ID = 1
        const val ACTION_STOP = "com.starsavior.helper.STOP"
        const val EXTRA_RESULT_CODE = "resultCode"
        const val EXTRA_RESULT_DATA = "resultData"

        fun start(context: Context, resultCode: Int, data: Intent) {
            val intent = Intent(context, OverlayService::class.java)
                .putExtra(EXTRA_RESULT_CODE, resultCode)
                .putExtra(EXTRA_RESULT_DATA, data)
            context.startForegroundService(intent)
        }
    }
}
