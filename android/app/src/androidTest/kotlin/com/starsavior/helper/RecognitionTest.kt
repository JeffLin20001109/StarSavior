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
    fun misreadTitleIsReadAgain() {
        // 實機：ML Kit 把「今日天氣－晴朗」整行讀成「SHRA-BARO」（標題後面是藍白條紋背景）；
        // 模擬器：同一張圖整行漏讀標題。兩種情況都要靠單獨重讀標題那一行找到事件。
        val frame = bitmap("journey_event_weather.jpg")
        val first = EventDetector.findEvent(ocr(frame))
        Log.i(TAG, "第一次辨識的標題：${first?.title}")
        // 存下重新辨識用的影像，CI 會打包成 artifact 方便檢查
        val dir = java.io.File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "ocr-debug").apply { mkdirs() }
        reader.debugImage = { name, image ->
            java.io.File(dir, "$name.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
        val boxes = reader.readEventArea(frame)
        reader.debugImage = null
        val event = EventDetector.findEvent(boxes)
        assertNotNull("OCR: ${boxes.map { it.text }}", event)
        assertEquals(EventKind.JOURNEY, event!!.kind)
        assertEquals(9, event.phase?.month)
        assertTrue("標題「${event.title}」與「今日天氣一晴朗」相似度不足",
            Text.similarity(event.title, "今日天氣一晴朗") >= Matching.MIN_SCORE)
    }

    /** 暫時的實驗：同一行標題用不同影像處理送進 ML Kit，記錄各自讀到什麼（不做斷言）。 */
    @Test
    fun titleExperiments() {
        org.opencv.android.OpenCVLoader.initLocal()
        val frame = bitmap("journey_event_weather.jpg")
        val region = EventDetector.scanRegion(frame.width, frame.height)
        val scan = Bitmap.createBitmap(frame, 0, 0, region.width, region.height)
        val label = EventDetector.findLabel(reader.read(scan)) ?: run { Log.i(TAG, "實驗：找不到標籤"); return }
        val area = EventDetector.titleArea(label, scan.width, scan.height)
        val line = Bitmap.createBitmap(scan, area.left, area.top, area.width, area.height)
        val labelCrop = EventDetector.titleCrop(label, scan.width, scan.height)
        val labelImage = Bitmap.createBitmap(scan, labelCrop.left, labelCrop.top, labelCrop.width, labelCrop.height)

        fun gray(b: Bitmap, scale: Double): org.opencv.core.Mat {
            val m = org.opencv.core.Mat()
            org.opencv.android.Utils.bitmapToMat(b, m)
            org.opencv.imgproc.Imgproc.cvtColor(m, m, org.opencv.imgproc.Imgproc.COLOR_RGBA2GRAY)
            org.opencv.imgproc.Imgproc.resize(m, m, org.opencv.core.Size(0.0, 0.0), scale, scale, org.opencv.imgproc.Imgproc.INTER_CUBIC)
            return m
        }
        fun binary(m: org.opencv.core.Mat): org.opencv.core.Mat = org.opencv.core.Mat().also {
            org.opencv.imgproc.Imgproc.threshold(m, it, 0.0, 255.0, org.opencv.imgproc.Imgproc.THRESH_BINARY_INV or org.opencv.imgproc.Imgproc.THRESH_OTSU)
        }
        fun pad(m: org.opencv.core.Mat, p: Int = 30): org.opencv.core.Mat = org.opencv.core.Mat().also {
            org.opencv.core.Core.copyMakeBorder(m, it, p, p, p, p, org.opencv.core.Core.BORDER_CONSTANT, org.opencv.core.Scalar(255.0))
        }
        fun toBitmap(m: org.opencv.core.Mat): Bitmap {
            val rgba = org.opencv.core.Mat()
            org.opencv.imgproc.Imgproc.cvtColor(m, rgba, org.opencv.imgproc.Imgproc.COLOR_GRAY2RGBA)
            return Bitmap.createBitmap(rgba.cols(), rgba.rows(), Bitmap.Config.ARGB_8888).also { org.opencv.android.Utils.matToBitmap(rgba, it) }
        }
        fun cols(m: org.opencv.core.Mat, from: Int, to: Int) = m.colRange(from.coerceIn(0, m.cols()), to.coerceIn(0, m.cols())).clone()
        fun hcat(vararg ms: org.opencv.core.Mat): org.opencv.core.Mat {
            val h = ms.maxOf { it.rows() }
            val fixed = ms.map { m -> if (m.rows() == h) m else org.opencv.core.Mat().also {
                org.opencv.core.Core.copyMakeBorder(m, it, 0, h - m.rows(), 0, 0, org.opencv.core.Core.BORDER_CONSTANT, org.opencv.core.Scalar(255.0)) } }
            return org.opencv.core.Mat().also { org.opencv.core.Core.hconcat(fixed, it) }
        }
        fun vcat(vararg ms: org.opencv.core.Mat) = org.opencv.core.Mat().also { org.opencv.core.Core.vconcat(ms.toList(), it) }

        val b1 = binary(gray(line, 1.0))
        val b2 = binary(gray(line, 2.0))
        val w2 = b2.cols()
        val textW = (b2.cols() * 0.55).toInt()  // 大約到「朗」為止，不含條紋
        val lab2 = binary(gray(labelImage, 2.0 * line.height / labelImage.height * 0.8))
        val dilated = org.opencv.core.Mat().also { org.opencv.imgproc.Imgproc.erode(b2, it, org.opencv.imgproc.Imgproc.getStructuringElement(org.opencv.imgproc.Imgproc.MORPH_RECT, org.opencv.core.Size(3.0, 3.0))) }
        val blurred = org.opencv.core.Mat().also { org.opencv.imgproc.Imgproc.GaussianBlur(b2, it, org.opencv.core.Size(5.0, 5.0), 0.0) }
        val trials = linkedMapOf(
            "原尺寸二值化" to pad(b1),
            "去條紋" to pad(cols(b2, 0, textW)),
            "左半" to pad(cols(b2, 0, textW / 2)),
            "右半" to pad(cols(b2, textW / 2, textW)),
            "前段四字" to pad(cols(b2, 0, (textW * 0.6).toInt())),
            "接在標籤後" to pad(hcat(lab2, org.opencv.core.Mat(b2.rows(), 40, b2.type(), org.opencv.core.Scalar(255.0)), cols(b2, 0, textW))),
            "標籤在上一行" to pad(vcat(pad(cols(lab2, 0, lab2.cols()), 0).let { l ->
                org.opencv.core.Mat().also { org.opencv.core.Core.copyMakeBorder(l, it, 0, 0, 0, maxOf(0, textW - l.cols()), org.opencv.core.Core.BORDER_CONSTANT, org.opencv.core.Scalar(255.0)) }
                    .let { if (it.cols() > textW) cols(it, 0, textW) else it } }, cols(b2, 0, textW))),
            "重複三行" to pad(vcat(cols(b2, 0, textW), cols(b2, 0, textW), cols(b2, 0, textW))),
            "加粗" to pad(cols(dilated, 0, textW)),
            "模糊" to pad(cols(blurred, 0, textW)),
            "整條加大邊" to pad(b2, 200),
        )
        val dir = java.io.File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "ocr-debug").apply { mkdirs() }
        for ((name, mat) in trials) {
            val image = toBitmap(mat)
            java.io.File(dir, "exp_$name.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
            val result = runCatching { reader.read(image).map { it.text } }.getOrElse { listOf("錯誤 $it") }
            Log.i(TAG, "實驗（$name，${image.width}x${image.height}）：$result")
        }
        Log.i(TAG, "實驗：二值化寬 $w2")
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
