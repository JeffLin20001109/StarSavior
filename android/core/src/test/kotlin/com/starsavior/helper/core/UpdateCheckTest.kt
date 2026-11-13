package com.starsavior.helper.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class UpdateCheckTest {
    @Test
    fun newerCommitIsReported() {
        assertEquals(
            UpdateCheck.Update("new", "https://example/app.apk"),
            UpdateCheck.newer("old", """{"commit": "new", "url": "https://example/app.apk"}"""),
        )
    }

    @Test
    fun sameCommitIsNotReported() {
        assertNull(UpdateCheck.newer("old", """{"commit": "old", "url": "x"}"""))
    }

    @Test
    fun badPayloadIsIgnored() {
        assertNull(UpdateCheck.newer("old", "not json"))
        assertNull(UpdateCheck.newer("old", """{"url": "x"}"""))
        assertNull(UpdateCheck.newer("old", "[]"))
    }

    private val perAbi = """{"commit": "new", "url": "https://example/arm64.apk",
        "urls": {"arm64-v8a": "https://example/arm64.apk", "x86_64": "https://example/x86_64.apk"}}"""

    @Test
    fun picksApkForDeviceAbi() {
        assertEquals("https://example/arm64.apk",
            UpdateCheck.newer("old", perAbi, listOf("arm64-v8a", "armeabi-v7a"))?.url)
        assertEquals("https://example/x86_64.apk",
            UpdateCheck.newer("old", perAbi, listOf("x86_64", "x86"))?.url)
        // 模擬器同時支援 x86_64 與 ARM 轉譯時，用它偏好的（排在前面的）
        assertEquals("https://example/x86_64.apk",
            UpdateCheck.newer("old", perAbi, listOf("x86_64", "arm64-v8a"))?.url)
    }

    @Test
    fun fallsBackToDefaultUrl() {
        // 沒有符合的 ABI，或是舊格式（只有 url）
        assertEquals("https://example/arm64.apk", UpdateCheck.newer("old", perAbi, listOf("mips"))?.url)
        assertEquals("https://example/arm64.apk", UpdateCheck.newer("old", perAbi)?.url)
    }

    @Test
    fun noCheckWithoutCurrentCommit() {
        assertNull(UpdateCheck.newer("", """{"commit": "new"}"""))
        assertNull(UpdateCheck.newer(null, """{"commit": "new"}"""))
    }
}
