package com.starsavior.helper.core

/** 從 OCR 結果找出事件標籤與標題（移植自 desktop/journey_helper/ocr.py）。 */
data class Box(val text: String, val x0: Double, val y0: Double, val x1: Double, val y1: Double) {
    val height: Double get() = y1 - y0
}

enum class EventKind { JOURNEY, ARCANA }

data class EventLabel(
    val kind: EventKind,
    val title: String,
    val label: Box,
    val titleBox: Box?,
    val phase: Text.Phase?,
)

data class Rect(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top
}

object EventDetector {
    /** 只辨識畫面左上角（寬 50%、高 45%）：事件標籤與日期都在這個範圍。 */
    fun scanRegion(width: Int, height: Int) = Rect(0, 0, (width * 0.5).toInt(), (height * 0.45).toInt())

    fun labelKind(text: String): EventKind? {
        val n = Text.norm(text)
        if ("旅程事件" in n || n == "旅程事" || n == "程事件") return EventKind.JOURNEY
        // 「阿爾克那事件」：OCR 偶爾會漏字，只要有「克那」或「尔克」加「事件」即可
        if ("事件" in n && ("克那" in n || "尔克" in n || "阿尔" in n)) return EventKind.ARCANA
        return null
    }

    /** boxes 需依由上到下、由左到右排序。找不到事件回傳 null。 */
    fun findEvent(boxes: List<Box>): EventLabel? {
        val phase = boxes.firstNotNullOfOrNull { Text.parsePhase(it.text) }
        for (label in boxes) {
            val kind = labelKind(label.text) ?: continue
            val h = maxOf(label.height, 1.0)
            // 標題緊接在標籤下方，左側大致對齊
            val below = boxes.filter { b ->
                b !== label &&
                    b.y0 >= label.y0 + 0.5 * h && b.y0 <= label.y1 + 1.6 * h &&
                    b.x0 >= label.x0 - 2.5 * h && b.x0 <= label.x0 + 4 * h &&
                    Text.norm(b.text).codePointCount(0, Text.norm(b.text).length) >= 2
            }
            val titleBox = below.minByOrNull { it.y0 }
            var title = titleBox?.text?.trim { it.isWhitespace() } ?: ""
            if (title.isEmpty()) {
                // OCR 把標籤與標題連在一起時，取「事件」後面的字
                val index = label.text.indexOf("事件")
                title = if (index >= 0) label.text.substring(index + 2).trim { it.isWhitespace() } else ""
            }
            if (title.isNotEmpty()) return EventLabel(kind, title, label, titleBox, phase)
        }
        return null
    }

    /** 阿爾克那事件左側的卡片圖範圍（整張畫面的座標）。 */
    fun cardCrop(width: Int, height: Int, label: Box): Rect {
        val mid = (label.y0 + label.y1) / 2
        val left = maxOf(0, (label.x0 - 0.18 * height).toInt())
        val right = maxOf(left + 8, (label.x0 - 0.004 * height).toInt())
        val top = maxOf(0, (mid - 0.125 * height).toInt())
        val bottom = minOf(height, (mid + 0.125 * height).toInt())
        return Rect(left, top, minOf(width, right), bottom)
    }
}
