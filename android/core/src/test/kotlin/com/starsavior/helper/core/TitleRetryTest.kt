package com.starsavior.helper.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class TitleRetryTest {
    @Test
    fun latinOnlyTitleIsMisread() {
        // 實機：ML Kit 把「今日天氣－晴朗」讀成「SHRA-BARO」
        assertTrue(EventDetector.titleLooksMisread("SHRA-BARO"))
        assertTrue(EventDetector.titleLooksMisread("ABC 123"))
    }

    @Test
    fun chineseTitleIsKept() {
        assertFalse(EventDetector.titleLooksMisread("今日天氣一晴朗"))
        assertFalse(EventDetector.titleLooksMisread("訓練的方向性"))
        assertFalse(EventDetector.titleLooksMisread("SHRA-BARO 晴"))  // 有一個中文字就不重讀
        assertFalse(EventDetector.titleLooksMisread(""))
    }

    @Test
    fun titleCropIsPaddedAndClamped() {
        val box = Box("x", 100.0, 50.0, 300.0, 70.0)
        assertEquals(Rect(93, 43, 307, 77), EventDetector.titleCrop(box, 1000, 1000))
        assertEquals(Rect(93, 43, 250, 60), EventDetector.titleCrop(box, 250, 60))
    }

    @Test
    fun replaceTitleSwapsOnlyThatLine() {
        val label = Box("旅程事件", 0.0, 0.0, 50.0, 10.0)
        val title = Box("SHRA-BARO", 0.0, 12.0, 80.0, 24.0)
        val boxes = EventDetector.replaceTitle(listOf(label, title), title, "今日天氣一晴朗")
        assertEquals(listOf("旅程事件", "今日天氣一晴朗"), boxes.map { it.text })
        assertEquals("今日天氣一晴朗", EventDetector.findEvent(boxes)?.title)
    }

    @Test
    fun missingTitleIsAddedBelowLabel() {
        // 模擬器：ML Kit 整行漏讀標題，只剩日期與標籤
        val date = Box("4@9月下句》", 330.0, 120.0, 520.0, 160.0)
        val label = Box("旅程事件", 402.0, 273.0, 517.0, 300.0)
        val boxes = listOf(date, label)
        assertEquals(null, EventDetector.findEvent(boxes))
        assertEquals(label, EventDetector.findLabel(boxes))
        val area = EventDetector.titleArea(label, 1304, 540)
        assertTrue(area.top >= 300 && area.bottom >= 348 && area.left <= 402 && area.right >= 655, "$area")
        val event = EventDetector.findEvent(EventDetector.addTitle(boxes, label, "今日天氣一晴朗"))
        assertEquals("今日天氣一晴朗", event?.title)
        assertEquals(EventKind.JOURNEY, event?.kind)
        assertEquals(Text.Phase(9, "late"), event?.phase)
    }

    @Test
    fun retriedTitleNoiseIsTrimmed() {
        assertEquals("今日天氣一晴朗", EventDetector.trimRetriedTitle("今日天氣一晴朗n"))
        assertEquals("訓練的方向性", EventDetector.trimRetriedTitle("'訓練的方向性"))
    }

    @Test
    fun dashReadAsChineseOneStillMatches() {
        // 實機：「今日天氣－打雷」讀成「今日天氣一打雷」只有 77% 相似度
        assertEquals(1.0, Text.similarity("今日天氣一打雷", "今日天氣－打雷"))
        assertEquals(1.0, Text.similarity("今曰天氣一打雷", "今日天氣－打雷"))  // 日 → 曰
        assertEquals(1.0, Text.similarity("今⽇天氣⼀打雷", "今日天氣－打雷"))  // 康熙部首
        assertEquals(1.0, Text.similarity("一起出發", "一起出發"))
        // 實機：「迷宮探勘」讀成「迷官採勘」只有 50%
        assertEquals(1.0, Text.similarity("迷官採勘", "迷宮探勘"))
        assertTrue(Text.similarity("今日天氣一打雷", "今日天氣－晴朗") < Matching.MIN_SCORE + 0.1)
    }

    @Test
    fun misreadTenDayPartIsParsed() {
        assertEquals(Text.Phase(9, "late"), Text.parsePhase("4@9月下句》"))
        assertEquals(Text.Phase(3, "early"), Text.parsePhase("3月上句"))
    }
}
