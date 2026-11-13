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
    private lateinit var updateBox: LinearLayout
    private var updateChecked = false
    private var updateStatus: TextView? = null
    private var updateButton: Button? = null
    private var pendingInstallUrl: String? = null
    private var installing = false
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
        updateBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = android.view.View.GONE
            setBackgroundColor(0xFFFFF4D6.toInt())
            setPadding(pad / 2, pad / 2, pad / 2, pad / 2)
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad * 2, pad, pad)
            setBackgroundColor(Color.WHITE)
            addView(title)
            addView(updateBox, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad / 2 })
            addView(help, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(start, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad / 2 })
            addView(battery, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
            addView(diagnostics, LinearLayout.LayoutParams(-1, -2).apply { topMargin = pad })
        }.let { content -> android.widget.ScrollView(this).apply { setBackgroundColor(Color.WHITE); addView(content) } })
        handleInstallStatus(intent)
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
        checkForUpdate()
        // 剛從「安裝未知應用程式」設定頁回來：允許了就繼續更新
        pendingInstallUrl?.let { url ->
            if (packageManager.canRequestPackageInstalls()) { pendingInstallUrl = null; downloadAndInstall(url) }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleInstallStatus(intent)
    }

    private fun handleInstallStatus(intent: Intent?) {
        if (intent?.action != AppUpdater.ACTION_INSTALL_STATUS) return
        val message = AppUpdater.handleStatus(this, intent) ?: return
        installing = false
        updateStatus?.text = message
        updateButton?.isEnabled = true
    }

    /** 背景下載 version.json；有新版本就在畫面上方顯示提示與下載按鈕。失敗時不顯示任何東西。 */
    private fun checkForUpdate() {
        val current = BuildConfig.BUILD_COMMIT
        if (current.isEmpty() || updateChecked) return
        updateChecked = true
        Thread {
            val found = runCatching {
                com.starsavior.helper.core.UpdateCheck.newer(current, Repository.httpGet(Repository.VERSION_URL))
            }.getOrNull() ?: return@Thread
            runOnUiThread { showUpdate(found.url.ifEmpty { Repository.APK_URL }) }
        }.start()
    }

    private fun showUpdate(url: String) {
        updateBox.removeAllViews()
        updateStatus = TextView(this).apply {
            text = "有新版本的旅程助手。按下方按鈕會在 App 內下載，接著由系統詢問是否安裝（會覆蓋目前的版本，設定不會消失）。"
            textSize = 15f; setTextColor(0xFF5C4400.toInt())
        }
        updateButton = Button(this).apply {
            text = "下載並安裝"; textSize = 16f
            setOnClickListener { downloadAndInstall(url) }
        }
        updateBox.addView(updateStatus)
        updateBox.addView(updateButton)
        updateBox.addView(Button(this).apply {
            text = "改用瀏覽器下載"; textSize = 13f
            setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
        })
        updateBox.visibility = android.view.View.VISIBLE
    }

    private fun downloadAndInstall(url: String) {
        if (installing) return
        if (!AppUpdater.ensureInstallAllowed(this)) {
            pendingInstallUrl = url
            updateStatus?.text = "請在設定頁開啟「允許安裝未知應用程式」，然後返回這裡，會自動繼續更新。"
            return
        }
        installing = true
        updateButton?.isEnabled = false
        updateStatus?.text = "正在下載新版…"
        Thread {
            try {
                val apk = AppUpdater.download(this, url) { percent ->
                    runOnUiThread { updateStatus?.text = if (percent >= 0) "正在下載新版… $percent%" else "正在下載新版…" }
                }
                runOnUiThread { updateStatus?.text = "下載完成，正在準備安裝…" }
                AppUpdater.install(this, apk)
            } catch (e: Exception) {
                runOnUiThread {
                    installing = false
                    updateButton?.isEnabled = true
                    updateStatus?.text = "更新失敗：${e.message}\n可以再試一次，或改用瀏覽器下載。"
                }
            }
        }.start()
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
