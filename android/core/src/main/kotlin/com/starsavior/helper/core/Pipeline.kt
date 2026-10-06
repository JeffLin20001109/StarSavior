package com.starsavior.helper.core

import kotlinx.serialization.json.JsonObject
import java.math.BigDecimal
import java.math.RoundingMode

/** 一次辨識的完整流程（移植自 desktop/journey_helper/pipeline.py）。OCR 與卡圖比對由平台提供。 */
data class Result(val title: String, val lines: List<Line>, val found: Boolean = false)

/** 卡圖比對結果：card 為明顯勝出的卡片；ranked 為 (配對點數, 卡片) 由高到低；failures 為無法取得卡圖的數量。 */
data class CardMatch(val card: JsonObject?, val ranked: List<Pair<Int, JsonObject>> = emptyList(), val failures: Int = 0)

fun interface CardIdentifier {
    /** crop：畫面中卡圖的範圍；candidates：要比對的卡片。 */
    fun best(crop: Rect, candidates: List<JsonObject>): CardMatch
}

class Pipeline(
    private val dataProvider: () -> GameData?,
    private val rendererFactory: (GameData) -> Renderer,
    private val difficulty: () -> String = { "" },
) {
    /** boxes：畫面左上角的 OCR 結果（整張畫面座標，依由上到下、由左到右排序）。 */
    fun run(boxes: List<Box>, width: Int, height: Int, cards: CardIdentifier): Result {
        val event = EventDetector.findEvent(boxes)
            ?: return message("沒有偵測到事件", "note",
                "畫面左上角沒有「旅程事件」或「阿爾克那事件」。",
                "辨識到的文字：" + boxes.take(8).joinToString("、") { it.text }.ifEmpty { "（沒有文字）" })
        val data = dataProvider()
            ?: return message("資料尚未就緒", "warn", "已辨識到事件「${event.title}」，但網站資料還沒取得，程式正在自動重試。")
        return if (event.kind == EventKind.JOURNEY) journey(event, data) else arcana(event, data, width, height, cards)
    }

    private fun journey(event: EventLabel, data: GameData): Result {
        val match = Matching.matchJourney(data, event.title, event.phase, difficulty())
        if (match.variants.isEmpty()) return notFound("旅程事件", event.title, match.alternatives)
        val lines = rendererFactory(data).render(listOf(Section(match.variants)))
        val header = mutableListOf(Line("旅程事件：${event.title}", "note"))
        if (match.score < 0.85) header.add(Line("（名稱相似度 ${percent(match.score)}，請確認是否為同一事件）", "warn"))
        return Result("旅程事件", header + lines, true)
    }

    private fun arcana(event: EventLabel, data: GameData, width: Int, height: Int, cards: CardIdentifier): Result {
        val ranked = Matching.arcanaTitleCandidates(data, event.title)
        // 先用卡圖辨識是哪一張卡，再找卡片中的這個事件
        val byTitle = ArrayList<JsonObject>()
        for (c in ranked) if (c.score >= Matching.MIN_SCORE && byTitle.none { it === c.card }) byTitle.add(c.card)
        val candidates = byTitle.ifEmpty { data.cards }
        val match = try {
            cards.best(EventDetector.cardCrop(width, height, event.label), candidates)
        } catch (e: Exception) {
            CardMatch(null)
        }
        var card = match.card
        val notes = ArrayList<String>()
        if (card == null && byTitle.isNotEmpty()) {
            // 卡圖無法確定：若標題只對應一張卡就直接用
            if (byTitle.size == 1) {
                card = byTitle[0]
                notes.add("（卡圖無法辨識，依事件名稱判斷）")
            } else if (match.ranked.isNotEmpty() && match.ranked[0].first >= 8) {
                card = match.ranked[0].second
                notes.add("（卡圖相似度偏低，請確認卡片是否正確）")
            }
        }
        if (card == null) {
            val names = byTitle.take(5).map { data.cardName(it) }
            if (names.isNotEmpty()) {
                return message("無法確定卡片", "warn", "事件「${event.title}」出現在多張卡片：", names.joinToString("、"),
                    "卡圖比對無法分辨，請確認遊戲畫面沒有被遮住。")
            }
            return notFound("阿爾克那事件", event.title,
                ranked.take(3).filter { it.score > 0.3 }.map { it.score to Text.loc(it.event["name"], "zh-TW") })
        }
        val (matched, score) = Matching.bestEventInCard(card, event.title)
        matched ?: return message("找不到事件", "warn", "卡片「${data.cardName(card)}」沒有任何事件資料。")
        if (score < Matching.MIN_SCORE - 0.1) notes.add("（這張卡找不到同名事件，顯示最接近的事件，相似度 ${percent(score)}）")
        // 只顯示目前遇到的事件（同名的多個版本一起列出）
        val sameName = card.objects("events").filter { it["name"] == matched["name"] }
        val renderer = rendererFactory(data)
        val cardKo = Text.loc(card["name"], "ko-KR")
        val charKo = Text.loc(card["char_name"], "ko-KR")
        val names = renderer.translator.translateMany(listOf(cardKo, charKo).filter { it.isNotEmpty() })
        val cardZh = if (cardKo.isNotEmpty()) names[cardKo] ?: cardKo else "?"
        val title = "阿爾克那：$cardZh" + (if (charKo.isNotEmpty()) "（${names[charKo] ?: charKo}）" else "")
        val header = mutableListOf(Line(title, "h2"), Line("事件：${event.title}", "note"))
        notes.forEach { header.add(Line(it, "warn")) }
        if (match.failures > 0) header.add(Line("（有 ${match.failures} 張卡圖無法下載）", "dim"))
        return Result("阿爾克那事件", header + renderer.render(listOf(Section(sameName.ifEmpty { listOf(matched) }))), true)
    }

    private fun notFound(kind: String, title: String, alternatives: List<Pair<Double, String>>): Result {
        val lines = mutableListOf(Line("$kind「$title」在網站資料中找不到。", "warn"))
        if (alternatives.isNotEmpty()) {
            lines.add(Line("最接近的事件：", "note"))
            alternatives.forEach { (score, name) -> lines.add(Line("・$name（${percent(score)}）", "dim")) }
        }
        lines.add(Line("可能是網站資料尚未更新，或辨識到的文字有誤。", "dim"))
        return Result("找不到事件", lines)
    }

    private fun message(title: String, style: String, vararg texts: String) = Result(title, texts.map { Line(it, style) })

    companion object {
        /** Python 的 f'{x:.0%}'。 */
        fun percent(value: Double): String = BigDecimal(value * 100).setScale(0, RoundingMode.HALF_EVEN).toPlainString() + "%"
    }
}
