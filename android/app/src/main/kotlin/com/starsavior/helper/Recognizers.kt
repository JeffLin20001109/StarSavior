package com.starsavior.helper

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.starsavior.helper.core.Box
import com.starsavior.helper.core.CardIdentifier
import com.starsavior.helper.core.CardMatch
import com.starsavior.helper.core.EventDetector
import com.starsavior.helper.core.Rect
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.calib3d.Calib3d
import org.opencv.core.Core
import org.opencv.core.Mat
import org.opencv.core.MatOfDMatch
import org.opencv.core.MatOfKeyPoint
import org.opencv.core.MatOfPoint2f
import org.opencv.core.Point
import org.opencv.core.Size
import org.opencv.features2d.BFMatcher
import org.opencv.features2d.SIFT
import org.opencv.imgproc.Imgproc
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/** 文字辨識：Google ML Kit 中文模型（內建於 APK，不需連網）。 */
class TextReader {
    private val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())

    /** 回傳每一行文字的範圍（以 bitmap 的座標），依由上到下、由左到右排序。需在背景執行緒呼叫。 */
    fun read(bitmap: Bitmap): List<Box> {
        val text = Tasks.await(recognizer.process(InputImage.fromBitmap(bitmap, 0)))
        return text.textBlocks.flatMap { it.lines }.mapNotNull { line ->
            val r = line.boundingBox ?: return@mapNotNull null
            Box(line.text, r.left.toDouble(), r.top.toDouble(), r.right.toDouble(), r.bottom.toDouble())
        }.sortedWith(compareBy({ it.y0 }, { it.x0 }))
    }

    /**
     * 辨識畫面左上角的事件區域。ML Kit 偶爾把整行中文標題誤讀成英文字母
     * （「今日天氣－晴朗」→「SHRA-BARO」），或整行漏讀；這時把標題那一行
     * 單獨裁下來、轉成白底黑字並放大後再辨識一次，讀到中文就用新的結果。
     */
    fun readEventArea(frame: Bitmap): List<Box> {
        val region = EventDetector.scanRegion(frame.width, frame.height)
        val scan = Bitmap.createBitmap(frame, 0, 0, region.width, region.height)
        val boxes = read(scan)
        val event = EventDetector.findEvent(boxes)
        if (event != null && !EventDetector.titleLooksMisread(event.title)) return boxes
        val label = event?.label ?: EventDetector.findLabel(boxes) ?: return boxes
        val titleBox = event?.titleBox
        val crop = if (titleBox != null) EventDetector.titleCrop(titleBox, scan.width, scan.height)
            else EventDetector.titleArea(label, scan.width, scan.height)
        if (crop.width < 8 || crop.height < 8) return boxes
        val line = Bitmap.createBitmap(scan, crop.left, crop.top, crop.width, crop.height)
        Log.i(TAG, "標籤 $label，重新辨識範圍 $crop（scan ${scan.width}x${scan.height}）")
        debugImage?.invoke("line", line)
        for ((name, variant) in lineVariants(line)) {
            debugImage?.invoke(name, variant)
            val lines = read(variant)
            val text = lines.firstOrNull { !EventDetector.titleLooksMisread(it.text) && it.text.isNotBlank() }
                ?.text?.trim { it.isWhitespace() } ?: ""
            Log.i(TAG, "標題「${event?.title}」沒讀到或被誤讀，重新辨識（$name）：${lines.map { it.text }} → 「$text」")
            if (text.isNotEmpty()) {
                return if (titleBox != null) EventDetector.replaceTitle(boxes, titleBox, text)
                    else EventDetector.addTitle(boxes, label, text)
            }
        }
        return boxes
    }

    /** 重新辨識用的幾種影像：白底黑字的二值化放大圖、灰階反白放大圖、原圖放大。 */
    private fun lineVariants(line: Bitmap): List<Pair<String, Bitmap>> {
        val scale = maxOf(2.0, 96.0 / line.height)
        val enlarged = Bitmap.createScaledBitmap(line, (line.width * scale).toInt(), (line.height * scale).toInt(), true)
        if (!openCv) return listOf("放大" to enlarged)
        fun convert(binary: Boolean): Bitmap {
            val mat = Mat()
            Utils.bitmapToMat(enlarged, mat)
            Imgproc.cvtColor(mat, mat, Imgproc.COLOR_RGBA2GRAY)
            if (binary) Imgproc.threshold(mat, mat, 0.0, 255.0, Imgproc.THRESH_BINARY_INV or Imgproc.THRESH_OTSU)
            else Core.bitwise_not(mat, mat)
            // 四周加白邊，ML Kit 對貼邊的文字比較容易漏讀
            val pad = (mat.rows() / 3).coerceAtLeast(8)
            Core.copyMakeBorder(mat, mat, pad, pad, pad, pad, Core.BORDER_CONSTANT, org.opencv.core.Scalar(255.0))
            Imgproc.cvtColor(mat, mat, Imgproc.COLOR_GRAY2RGBA)
            val out = Bitmap.createBitmap(mat.cols(), mat.rows(), Bitmap.Config.ARGB_8888)
            Utils.matToBitmap(mat, out)
            mat.release()
            return out
        }
        return listOf("二值化" to convert(true), "灰階反白" to convert(false), "放大" to enlarged)
    }

    private val openCv by lazy { OpenCVLoader.initLocal() }

    /** 測試用：取得重新辨識時送進 ML Kit 的影像。 */
    var debugImage: ((String, Bitmap) -> Unit)? = null

    fun close() = recognizer.close()

    companion object {
        private const val TAG = "TextReader"
    }
}

/**
 * 卡圖比對：把遊戲左上角的小卡圖與網站卡圖做 SIFT 特徵比對（對應 Windows 版 cards.py）。
 * 只在明顯勝出時回傳卡片。
 */
class CardMatcher(private val loadImage: (JsonObject) -> ByteArray) {
    private val ready = OpenCVLoader.initLocal()
    private val cache = ConcurrentHashMap<String, Pair<MatOfKeyPoint, Mat>>()
    private val pool = Executors.newFixedThreadPool(4)

    fun identifier(frame: Bitmap): CardIdentifier = CardIdentifier { crop, candidates -> best(frame, crop, candidates) }

    private fun best(frame: Bitmap, crop: Rect, candidates: List<JsonObject>): CardMatch {
        if (!ready || crop.width <= 8 || crop.height <= 8) return CardMatch(null)
        val query = features(Bitmap.createBitmap(frame, crop.left, crop.top, crop.width, crop.height))
        var failures = 0
        val futures = candidates.map { card -> pool.submit<Pair<Int, JsonObject>?> {
            try {
                inliers(reference(card), query) to card
            } catch (e: Exception) {
                Log.w(TAG, "卡圖 ${card["id"]} 無法使用", e)
                null
            }
        } }
        val ranked = futures.mapNotNull { it.get() ?: run { failures++; null } }.sortedByDescending { it.first }
        val top = ranked.firstOrNull()?.first ?: 0
        val second = ranked.getOrNull(1)?.first ?: 0
        val card = if (top >= MIN_INLIERS && top >= 2 * second + 4) ranked[0].second else null
        return CardMatch(card, ranked, failures)
    }

    private fun reference(card: JsonObject): Pair<MatOfKeyPoint, Mat> {
        val key = (card["id"] as? JsonPrimitive)?.content ?: Repository.cardImageUrl(card)
        return cache.getOrPut(key) {
            val bytes = loadImage(card)
            val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: error("卡圖無法解碼")
            features(bitmap)
        }
    }

    private fun features(bitmap: Bitmap): Pair<MatOfKeyPoint, Mat> {
        val rgba = Mat()
        Utils.bitmapToMat(bitmap.copy(Bitmap.Config.ARGB_8888, false), rgba)
        val gray = Mat()
        Imgproc.cvtColor(rgba, gray, Imgproc.COLOR_RGBA2GRAY)
        val scale = NORMAL_HEIGHT.toDouble() / gray.rows()
        val resized = Mat()
        Imgproc.resize(gray, resized, Size(maxOf(1.0, Math.round(gray.cols() * scale).toDouble()), NORMAL_HEIGHT.toDouble()), 0.0, 0.0,
            if (scale < 1) Imgproc.INTER_AREA else Imgproc.INTER_CUBIC)
        val points = MatOfKeyPoint()
        val descriptors = Mat()
        SIFT.create(2000, 3, 0.01, 10.0, 1.6).detectAndCompute(resized, Mat(), points, descriptors)
        return points to descriptors
    }

    /** 符合同一透視變換的配對點數。 */
    private fun inliers(reference: Pair<MatOfKeyPoint, Mat>, query: Pair<MatOfKeyPoint, Mat>): Int {
        val (refPoints, refDesc) = reference
        val (qPoints, qDesc) = query
        if (refDesc.rows() < 2 || qDesc.rows() < 2) return 0
        val matches = ArrayList<MatOfDMatch>()
        BFMatcher.create().knnMatch(refDesc, qDesc, matches, 2)
        val good = matches.mapNotNull { m ->
            val pair = m.toArray()
            if (pair.size == 2 && pair[0].distance < 0.75 * pair[1].distance) pair[0] else null
        }
        if (good.size < 6) return 0
        val refArr = refPoints.toArray()
        val qArr = qPoints.toArray()
        val src = MatOfPoint2f(*good.map { Point(refArr[it.queryIdx].pt.x, refArr[it.queryIdx].pt.y) }.toTypedArray())
        val dst = MatOfPoint2f(*good.map { Point(qArr[it.trainIdx].pt.x, qArr[it.trainIdx].pt.y) }.toTypedArray())
        val mask = Mat()
        val h = Calib3d.findHomography(src, dst, Calib3d.RANSAC, 5.0, mask)
        if (h.empty() || mask.empty()) return 0
        return Core.countNonZero(mask)
    }

    companion object {
        private const val TAG = "CardMatcher"
        private const val NORMAL_HEIGHT = 480
        private const val MIN_INLIERS = 12
    }
}
