package com.starsavior.helper.core

import kotlin.test.Test
import kotlin.test.assertEquals

class DownloadResumeTest {
    @Test
    fun resumesWhenServerHonoursRange() {
        assertEquals(1000, DownloadResume.resumeFrom(1000, 206, "bytes 1000-4999/5000"))
    }

    @Test
    fun startsOverWhenServerIgnoresRange() {
        assertEquals(0, DownloadResume.resumeFrom(1000, 200, null))
        assertEquals(0, DownloadResume.resumeFrom(1000, 206, "bytes 0-4999/5000"))
        assertEquals(0, DownloadResume.resumeFrom(1000, 206, null))
    }

    @Test
    fun freshDownloadStartsAtZero() {
        assertEquals(0, DownloadResume.resumeFrom(0, 200, null))
    }

    @Test
    fun totalSizeFromContentRangeOrLength() {
        assertEquals(5000, DownloadResume.totalSize(206, "bytes 1000-4999/5000", 4000))
        assertEquals(5000, DownloadResume.totalSize(200, null, 5000))
        assertEquals(-1, DownloadResume.totalSize(200, null, -1))
        assertEquals(4000, DownloadResume.totalSize(206, "bytes 1000-4999/*", 4000))
    }

    @Test
    fun backoffGrowsAndIsCapped() {
        assertEquals(2_000, DownloadResume.backoffMs(1))
        assertEquals(4_000, DownloadResume.backoffMs(2))
        assertEquals(8_000, DownloadResume.backoffMs(3))
        assertEquals(15_000, DownloadResume.backoffMs(4))
        assertEquals(15_000, DownloadResume.backoffMs(10))
    }
}
