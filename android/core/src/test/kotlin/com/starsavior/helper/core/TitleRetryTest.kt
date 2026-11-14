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
}
