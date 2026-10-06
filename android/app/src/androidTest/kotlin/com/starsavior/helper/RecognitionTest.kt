package com.starsavior.helper

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.starsavior.helper.core.EventDetector
import com.starsavior.helper.core.EventKind
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith

/** 在模擬器上用真實遊戲截圖（shared/fixtures）測試 ML Kit 文字辨識與 OpenCV 卡圖比對。 */
@RunWith(AndroidJUnit4::class)
class RecognitionTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets

    private fun bitmap(name: String): Bitmap = assets.open(name).use { BitmapFactory.decodeStream(it) }
    private fun bytes(name: String): ByteArray = assets.open(name).use { it.readBytes() }

    private fun detect(name: String) = bitmap(name).let { frame ->
        val region = EventDetector.scanRegion(frame.width, frame.height)
        val boxes = TextReader().read(Bitmap.createBitmap(frame, 0, 0, region.width, region.height))
        frame to EventDetector.findEvent(boxes)
    }

    @Test
    fun journeyEventTitleIsRecognized() {
        val (_, event) = detect("journey_event.jpg")
        assertNotNull(event)
        assertEquals(EventKind.JOURNEY, event!!.kind)
        assertEquals("訓練的方向性", event.title)
        assertEquals(3, event.phase?.month)
    }

    @Test
    fun arcanaEventTitleAndCardAreRecognized() {
        val (frame, event) = detect("arcana_event.jpg")
        assertNotNull(event)
        assertEquals(EventKind.ARCANA, event!!.kind)
        assertEquals("請講關於初戀的故事", event.title)
        val files = mapOf("1" to "card_elisa.jpg", "2" to "card_ling.jpg", "3" to "card_other.jpg")
        val cards = files.keys.map { JsonObject(mapOf("id" to JsonPrimitive(it.toInt()))) }
        val matcher = CardMatcher { card -> bytes(files.getValue((card["id"] as JsonPrimitive).content)) }
        val crop = EventDetector.cardCrop(frame.width, frame.height, event.label)
        val match = matcher.identifier(frame).best(crop, cards)
        assertEquals("1", (match.card?.get("id") as? JsonPrimitive)?.content)
    }
}
