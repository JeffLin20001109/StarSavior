package com.starsavior.helper

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.TextPaint
import android.text.method.LinkMovementMethod
import android.text.style.ClickableSpan
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.starsavior.helper.core.Line
import com.starsavior.helper.core.Result
import kotlin.math.abs

private fun Context.dp(value: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, resources.displayMetrics).toInt()

private fun overlayParams(width: Int, height: Int, focusable: Boolean = false) = WindowManager.LayoutParams(
    width, height, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
    (if (focusable) 0 else WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE) or
        WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
    PixelFormat.TRANSLUCENT,
).apply { gravity = Gravity.TOP or Gravity.START }

/** 懸浮的「旅」按鈕：點一下辨識，拖曳移動，長按結束。 */
@SuppressLint("ClickableViewAccessibility")
class FloatingButton(
    private val context: Context,
    private val wm: WindowManager,
    private val onTap: () -> Unit,
    private val onLongPress: () -> Unit,
    private val onMoved: (x: Int, y: Int) -> Unit,
) {
    private val size = context.dp(52f)
    private val circle = GradientDrawable().apply {
        shape = GradientDrawable.OVAL
        setColor(COLOR_READY)
        setStroke(context.dp(2f), Color.WHITE)
    }
    val view = TextView(context).apply {
        text = "旅"
        setTextColor(Color.WHITE)
        textSize = 20f
        typeface = Typeface.DEFAULT_BOLD
        gravity = Gravity.CENTER
        background = circle
        alpha = 0.92f
    }
    val params = overlayParams(size, size)

    init {
        val slop = ViewConfiguration.get(context).scaledTouchSlop
        val longPress = ViewConfiguration.getLongPressTimeout().toLong()
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        var moved = false
        val longPressRunnable = Runnable { if (!moved) { moved = true; onLongPress() } }
        view.setOnTouchListener { _, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY; startX = params.x; startY = params.y; moved = false
                    view.postDelayed(longPressRunnable, longPress)
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX
                    val dy = e.rawY - downY
                    if (!moved && (abs(dx) > slop || abs(dy) > slop)) { moved = true; view.removeCallbacks(longPressRunnable) }
                    if (moved) {
                        params.x = startX + dx.toInt(); params.y = startY + dy.toInt()
                        wm.updateViewLayout(view, params)
                    }
                }
                MotionEvent.ACTION_UP -> {
                    view.removeCallbacks(longPressRunnable)
                    if (!moved) onTap() else onMoved(params.x, params.y)
                }
                MotionEvent.ACTION_CANCEL -> view.removeCallbacks(longPressRunnable)
            }
            true
        }
    }

    fun setBusy(busy: Boolean) {
        circle.setColor(if (busy) COLOR_BUSY else COLOR_READY)
        view.text = if (busy) "…" else "旅"
    }

    val sizePx: Int get() = size

    companion object {
        private const val COLOR_READY = 0xFF3B6FD8.toInt()
        private const val COLOR_BUSY = 0xFFE08A1E.toInt()
    }
}

/** 結果小窗：標題列（可拖曳、✕ 關閉）＋可捲動內容；依難度不同的結果可點 ▶ 展開。 */
@SuppressLint("ClickableViewAccessibility", "SetTextI18n")
class ResultPopup(private val context: Context, private val wm: WindowManager) {
    private val title = TextView(context).apply {
        setTextColor(Color.WHITE); textSize = 15f; typeface = Typeface.DEFAULT_BOLD
        setPadding(context.dp(10f), context.dp(6f), context.dp(6f), context.dp(6f))
    }
    private val close = TextView(context).apply {
        text = " ✕ "; setTextColor(Color.WHITE); textSize = 17f; typeface = Typeface.DEFAULT_BOLD
        setPadding(context.dp(8f), context.dp(4f), context.dp(10f), context.dp(4f))
    }
    private val body = TextView(context).apply {
        setTextColor(0xFF202020.toInt()); textSize = 14f
        setPadding(context.dp(12f), context.dp(8f), context.dp(12f), context.dp(10f))
        movementMethod = LinkMovementMethod.getInstance()
        highlightColor = Color.TRANSPARENT
        setLineSpacing(context.dp(2f).toFloat(), 1f)
    }
    private val scroll = ScrollView(context).apply { addView(body); setBackgroundColor(Color.WHITE) }
    val view = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        background = GradientDrawable().apply { setColor(0xFF3B6FD8.toInt()); cornerRadius = context.dp(6f).toFloat() }
        setPadding(context.dp(2f), 0, context.dp(2f), context.dp(2f))
        val header = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(title, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(close)
        }
        addView(header)
        addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
    }
    private val params = overlayParams(0, 0)
    var visible = false
        private set
    private var lines: List<Line> = emptyList()
    private val folds = HashMap<Int, Boolean>()

    init {
        close.setOnClickListener { hide() }
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        title.setOnTouchListener { _, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> { downX = e.rawX; downY = e.rawY; startX = params.x; startY = params.y }
                MotionEvent.ACTION_MOVE -> {
                    params.x = startX + (e.rawX - downX).toInt(); params.y = startY + (e.rawY - downY).toInt()
                    if (visible) wm.updateViewLayout(view, params)
                }
            }
            true
        }
    }

    /** anchor：按鈕位置與大小；screenW/H：螢幕大小。 */
    fun show(result: Result, anchorX: Int, anchorY: Int, anchorSize: Int, screenW: Int, screenH: Int) {
        title.text = result.title
        lines = result.lines
        folds.clear()
        lines.forEach { line -> line.fold?.takeIf { it.head }?.let { folds[it.id] = it.collapsed } }
        rebuild()
        val landscape = screenW > screenH
        params.width = if (landscape) (screenW * 0.42).toInt() else (screenW * 0.92).toInt()
        params.height = (screenH * if (landscape) 0.85 else 0.6).toInt()
        params.x = if (landscape) {
            if (anchorX + anchorSize / 2 > screenW / 2) anchorX - params.width - context.dp(8f) else anchorX + anchorSize + context.dp(8f)
        } else (screenW - params.width) / 2
        params.x = params.x.coerceIn(0, maxOf(0, screenW - params.width))
        params.y = if (landscape) (anchorY - context.dp(40f)).coerceIn(0, maxOf(0, screenH - params.height))
        else if (anchorY > screenH / 2) context.dp(24f) else screenH - params.height - context.dp(24f)
        if (visible) wm.updateViewLayout(view, params) else wm.addView(view, params)
        visible = true
        scroll.scrollTo(0, 0)
    }

    fun hide() {
        if (visible) wm.removeView(view)
        visible = false
    }

    fun setHiddenForCapture(hidden: Boolean) {
        if (visible) view.visibility = if (hidden) View.INVISIBLE else View.VISIBLE
    }

    private fun rebuild() {
        val text = SpannableStringBuilder()
        var first = true
        for (line in lines) {
            val fold = line.fold
            if (fold != null && !fold.head && folds[fold.id] == true) continue  // 收起的內容
            if (!first) text.append('\n')
            first = false
            val lineStart = text.length
            for (segment in line.segments) {
                var value = segment.text
                if (fold != null && fold.head) {
                    value = value.replaceFirst(Regex("[▶▼]"), if (folds[fold.id] == true) "▶" else "▼")
                }
                val start = text.length
                text.append(value)
                style(text, start, text.length, segment.style)
            }
            if (fold != null && fold.head) {
                val id = fold.id
                text.setSpan(object : ClickableSpan() {
                    override fun onClick(widget: View) {
                        folds[id] = !(folds[id] ?: false)
                        rebuild()
                    }
                    override fun updateDrawState(ds: TextPaint) { ds.isUnderlineText = false }
                }, lineStart, text.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        body.text = text
    }

    private fun style(text: SpannableStringBuilder, start: Int, end: Int, style: String) {
        val (color, size, bold) = STYLES[style] ?: STYLES.getValue("effect")
        text.setSpan(ForegroundColorSpan(color), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        if (size != 1f) text.setSpan(RelativeSizeSpan(size), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        if (bold) text.setSpan(StyleSpan(Typeface.BOLD), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
    }

    companion object {
        /** 與 Windows 版小窗相同的配色。 */
        private val STYLES = mapOf(
            "h1" to Triple(0xFF1D3F8F.toInt(), 1.18f, true),
            "h2" to Triple(0xFF6A3FB5.toInt(), 1.1f, true),
            "choice" to Triple(0xFF0B6E4F.toInt(), 1.0f, true),
            "effect" to Triple(0xFF202020.toInt(), 1.0f, false),
            "note" to Triple(0xFF4A4F57.toInt(), 0.92f, false),
            "warn" to Triple(0xFFB3261E.toInt(), 0.92f, false),
            "dim" to Triple(0xFF5F6670.toInt(), 0.85f, false),
            "special" to Triple(0xFF9A7400.toInt(), 1.0f, false),
            "minus" to Triple(0xFFC62828.toInt(), 1.0f, false),
        )
    }
}
