package com.starsavior.helper

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Build
import android.os.Handler
import android.util.DisplayMetrics
import android.view.WindowManager

/**
 * 透過 MediaProjection 擷取整個螢幕。VirtualDisplay 只建立一次（Android 14 起每次授權只能建立一次），
 * 螢幕方向或解析度改變時改用 resize 調整大小。
 */
class ScreenCapturer(
    private val context: Context,
    private val projection: MediaProjection,
    private val handler: Handler,
    onStopped: () -> Unit,
) {
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var width = 0
    private var height = 0
    @Volatile private var releasing = false

    init {
        // Android 14 起必須先註冊；使用者從系統停止擷取時通知服務結束
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                if (!releasing) onStopped()  // 自己呼叫 release() 時不通知
            }
        }, handler)
        val (w, h, dpi) = screenSize()
        width = w
        height = h
        reader = newReader(w, h)
        display = projection.createVirtualDisplay("StarSaviorHelper", w, h, dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader!!.surface, null, handler)
    }

    @SuppressLint("WrongConstant")
    private fun newReader(w: Int, h: Int) = ImageReader.newInstance(w, h, PixelFormat.RGBA_8888, 2)

    private fun screenSize(): Triple<Int, Int, Int> {
        val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dpi = context.resources.displayMetrics.densityDpi
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val bounds = wm.maximumWindowMetrics.bounds
            Triple(bounds.width(), bounds.height(), dpi)
        } else {
            val metrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            wm.defaultDisplay.getRealMetrics(metrics)
            Triple(metrics.widthPixels, metrics.heightPixels, dpi)
        }
    }

    /** 螢幕大小改變（例如轉成橫向）時調整擷取大小；回傳是否有調整（需等下一個畫面）。 */
    fun syncSize(): Boolean {
        val (w, h, dpi) = screenSize()
        if (w == width && h == height) return false
        width = w
        height = h
        val old = reader
        reader = newReader(w, h)
        display?.resize(w, h, dpi)
        display?.surface = reader!!.surface
        old?.close()
        return true
    }

    /** 取得最新畫面；尚無畫面時回傳 null。 */
    fun latest(): Bitmap? {
        val image = reader?.acquireLatestImage() ?: return null
        try {
            val plane = image.planes[0]
            val pixelStride = plane.pixelStride
            val rowPadding = plane.rowStride - pixelStride * image.width
            val padded = Bitmap.createBitmap(image.width + rowPadding / pixelStride, image.height, Bitmap.Config.ARGB_8888)
            padded.copyPixelsFromBuffer(plane.buffer)
            return if (rowPadding == 0) padded else Bitmap.createBitmap(padded, 0, 0, image.width, image.height)
        } finally {
            image.close()
        }
    }

    fun release() {
        releasing = true
        display?.release()
        reader?.close()
        projection.stop()
    }
}
