package com.starsavior.helper

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** 啟動畫面：取得懸浮窗與螢幕擷取權限後啟動前景服務，接著回到遊戲。 */
class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var battery: Button
    private lateinit var diagnostics: TextView
    private var askedNotifications = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (resources.displayMetrics.density * 20).toInt()
        val title = TextView(this).apply {
            text = "StarSavior 旅程助手"; textSize = 22f; typeface = Typeface.DEFAULT_BOLD; setTextColor(0xFF1D3F8F.toInt())
        }
        val help = TextView(this).apply {
            textSize = 15f; setTextColor(0xFF333333.toInt())
            text = "按「啟動」後會在畫面上出現藍色的「旅」按鈕。\n\n" +
                "・遇到旅程事件或阿爾克那事件時，點一下按鈕。\n" +
                "・拖曳按鈕可以移動位置。\n" +
                "・長按按鈕，或在通知列按「結束」即可關閉。\n\n" +
                "第一次使用需要允許「顯示在其他應用程式上層」與「螢幕擷取」。"
        }
        status = TextView(this).apply { textSize = 14f; setTextColor(0xFFB3261E.toInt()) }
        val start = Button(this).apply { text = "啟動"; textSize = 18f; setOnClickListener { begin() } }
        battery = Button(this).apply {
            text = "不要對旅程助手省電（避免被系統關閉）"; textSize = 14f
            setOnClickListener { requestBatteryExemption() }
        }
        diagnostics = TextView(this).apply { textSize = 12f; setTextColor(0xFF5F6670.toInt()); setTextIsSelectable(true) }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad * 2, pad, pad)
            setBackgroundColor(Color.WHITE)
            addView(title)
            addView(help, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(start, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad / 2 })
            addView(battery, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(diagnostics, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
        }.let { content -> android.widget.ScrollView(this).apply { setBackgroundColor(Color.WHITE); addView(content) } })
    }

    override fun onResume() {
        super.onResume()
        val power = getSystemService(POWER_SERVICE) as android.os.PowerManager
        battery.visibility = if (power.isIgnoringBatteryOptimizations(packageName)) android.view.View.GONE else android.view.View.VISIBLE
        // 診斷資訊：上次為什麼結束（系統紀錄）、當機訊息、最近的事件
        val parts = mutableListOf<String>()
        Diagnostics.lastExitReason(this)?.let { parts += "上次結束原因：$it" }
        Diagnostics.lastCrash(this)?.let { parts += "上次當機紀錄：\n$it" }
        Diagnostics.recentEvents(this).takeIf { it.isNotEmpty() }?.let { parts += "最近的事件：\n" + it.joinToString("\n") }
        diagnostics.text = if (parts.isEmpty()) "" else "── 診斷資訊（遇到問題時可以截圖回報）──\n" + parts.joinToString("\n\n")
    }

    @android.annotation.SuppressLint("BatteryLife")
    private fun requestBatteryExemption() {
        startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
    }

    private fun begin() {
        if (!Settings.canDrawOverlays(this)) {
            status.text = "請允許「顯示在其他應用程式上層」，然後回到這裡再按一次「啟動」。"
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            return
        }
        if (Build.VERSION.SDK_INT >= 33 && !askedNotifications &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            askedNotifications = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
            return
        }
        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        @Suppress("DEPRECATION")
        startActivityForResult(mpm.createScreenCaptureIntent(), REQUEST_CAPTURE)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_NOTIFICATIONS) begin()  // 通知權限非必要，拒絕也繼續
    }

    @Deprecated("Activity 的舊式回呼；這裡沒有使用 AndroidX")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_CAPTURE) return
        if (resultCode != RESULT_OK || data == null) {
            status.text = "需要允許螢幕擷取才能辨識遊戲畫面。"
            return
        }
        OverlayService.start(this, resultCode, data)
        moveTaskToBack(true)  // 回到遊戲
    }

    companion object {
        private const val REQUEST_CAPTURE = 1
        private const val REQUEST_NOTIFICATIONS = 2
    }
}
