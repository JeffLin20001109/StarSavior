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

    @Test
    fun noCheckWithoutCurrentCommit() {
        assertNull(UpdateCheck.newer("", """{"commit": "new"}"""))
        assertNull(UpdateCheck.newer(null, """{"commit": "new"}"""))
    }
}
