package com.starsavior.helper

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.widget.Toast

/** 透明的畫面：只用來重新取得「螢幕擷取」授權（系統停止擷取後，從懸浮按鈕叫出）。 */
class CaptureActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        @Suppress("DEPRECATION")
        startActivityForResult(mpm.createScreenCaptureIntent(), REQUEST_CAPTURE)
    }

    @Deprecated("Activity 的舊式回呼；這裡沒有使用 AndroidX")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CAPTURE && resultCode == RESULT_OK && data != null) {
            OverlayService.start(this, resultCode, data)
        } else {
            Toast.makeText(this, "沒有允許螢幕擷取，無法辨識遊戲畫面", Toast.LENGTH_LONG).show()
        }
        finish()
    }

    companion object {
        private const val REQUEST_CAPTURE = 1
    }
}
