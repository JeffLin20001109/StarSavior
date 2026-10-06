package com.starsavior.helper

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.starsavior.helper.core.EventDetector
import com.starsavior.helper.core.EventKind
import com.starsavior.helper.core.GameData
import com.starsavior.helper.core.Matching
import com.starsavior.helper.core.Pipeline
import com.starsavior.helper.core.Renderer
import com.starsavior.helper.core.TableTranslator
import com.starsavior.helper.core.Text
import com.starsavior.helper.core.parseJson
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * 在模擬器上用真實遊戲截圖（shared/fixtures）測試 ML Kit 文字辨識與 OpenCV 卡圖比對，
 * 並跑完整流程，確認顯示的是正確的事件（OCR 偶有錯字，靠模糊比對找到事件）。
 */
@RunWith(AndroidJUnit4::class)
class RecognitionTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets
    private val reader = TextReader()

    private fun bitmap(name: String): Bitmap = assets.open(name).use { BitmapFactory.decodeStream(it) }
    private fun bytes(name: String): ByteArray = assets.open(name).use { it.readBytes() }

    private fun ocr(frame: Bitmap) = EventDetector.scanRegion(frame.width, frame.height).let { region ->
        reader.read(Bitmap.createBitmap(frame, 0, 0, region.width, region.height)).also { boxes ->
            Log.i(TAG, "OCR: " + boxes.joinToString(" | ") { it.text })
        }
    }

    private val data by lazy { GameData(assets.open("sample_data.json").use { parseJson(it.reader().readText()) }.jsonObject) }
    private val files = mapOf("1" to "card_elisa.jpg", "2" to "card_ling.jpg", "3" to "card_other.jpg")
    private val matcher = CardMatcher { card -> bytes(files.getValue((card["id"] as JsonPrimitive).content)) }
    private val pipeline = Pipeline({ data }, { Renderer(it, TableTranslator(emptyMap())) })

    @Test
    fun journeyEventIsRecognizedAndMatched() {
        val frame = bitmap("journey_event.jpg")
        val boxes = ocr(frame)
        val event = EventDetector.findEvent(boxes)
        assertNotNull("OCR: ${boxes.map { it.text }}", event)
        assertEquals(EventKind.JOURNEY, event!!.kind)
        assertEquals(3, event.phase?.month)
        assertTrue("標題「${event.title}」與「訓練的方向性」相似度不足",
            Text.similarity(event.title, "訓練的方向性") >= Matching.MIN_SCORE)
        val result = pipeline.run(boxes, frame.width, frame.height, matcher.identifier(frame))
        assertTrue(result.found)
        assertTrue(result.lines.joinToString("\n") { it.text }.contains("훈련의 방향성"))
    }

    @Test
    fun arcanaEventCardIsIdentifiedByImage() {
        val frame = bitmap("arcana_event.jpg")
        val boxes = ocr(frame)
        val event = EventDetector.findEvent(boxes)
        assertNotNull("OCR: ${boxes.map { it.text }}", event)
        assertEquals(EventKind.ARCANA, event!!.kind)
        // 卡圖比對：B 圖左上角的小卡圖應該對應到艾莉莎的卡（card_elisa）
        val cards = files.keys.map { JsonObject(mapOf("id" to JsonPrimitive(it.toInt()))) }
        val crop = EventDetector.cardCrop(frame.width, frame.height, event.label)
        val match = matcher.identifier(frame).best(crop, cards)
        Log.i(TAG, "card ranking: " + match.ranked.map { it.first to it.second["id"] })
        assertEquals("1", (match.card?.get("id") as? JsonPrimitive)?.content)
        // 完整流程：事件名稱同時出現在兩張卡，要靠卡圖選出卡片 1
        val result = pipeline.run(boxes, frame.width, frame.height, matcher.identifier(frame))
        val text = result.lines.joinToString("\n") { it.text }
        assertTrue(text, result.found)
        assertTrue(text, text.contains("하늘의 시험"))
        assertTrue(text, text.contains("첫사랑 얘기 해주세요"))
    }

    companion object {
        private const val TAG = "RecognitionTest"
    }
}
