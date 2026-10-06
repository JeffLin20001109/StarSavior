package com.starsavior.helper.core

import kotlinx.serialization.json.JsonObject

/** 用繁體中文事件名稱比對網站資料（移植自 desktop/journey_helper/matching.py）。 */
object Matching {
    const val MIN_SCORE = 0.6

    /** 比對用的名稱：繁中為主，簡中為備用（網站有些條目缺繁中）。 */
    private fun names(variant: JsonObject): List<String> =
        listOf(Text.loc(variant["name"], "zh-TW"), Text.loc(variant["name"], "zh-CN")).filter { it.isNotEmpty() }

    fun variantScore(variant: JsonObject, title: String): Double =
        names(variant).maxOfOrNull { Text.similarity(title, it) } ?: 0.0

    data class JourneyMatch(
        val score: Double,
        val variants: List<JsonObject>,
        val alternatives: List<Pair<Double, String>> = emptyList(),
        val phaseMatched: Boolean = false,
    )

    fun matchJourney(data: GameData, title: String, phase: Text.Phase?, difficulty: String = ""): JourneyMatch {
        val ranked = data.journeyGroups
            .map { group -> (group.maxOfOrNull { variantScore(it, title) } ?: 0.0) to group }
            .sortedByDescending { it.first }
        fun firstName(group: List<JsonObject>) = names(group[0]).firstOrNull() ?: "?"
        if (ranked.isEmpty() || ranked[0].first < MIN_SCORE) {
            val alternatives = ranked.take(3).filter { it.first > 0.3 }.map { it.first to firstName(it.second) }
            return JourneyMatch(ranked.firstOrNull()?.first ?: 0.0, emptyList(), alternatives)
        }
        val score = ranked[0].first
        // 同名但分在不同群組的事件一起顯示
        var variants = ranked.filter { it.first >= score - 1e-6 }.flatMap { it.second }
        variants = filterDifficulty(variants, difficulty)
        val (filtered, matched) = filterPhase(variants, phase)
        val alternatives = ranked.drop(1).take(3).filter { it.first >= MIN_SCORE - 0.15 }.map { it.first to firstName(it.second) }
        return JourneyMatch(score, filtered, alternatives, matched)
    }

    fun filterDifficulty(variants: List<JsonObject>, difficulty: String): List<JsonObject> {
        if (difficulty.isEmpty()) return variants
        val kept = variants.filter { v ->
            val tiers = v["difficulties"].arr()?.map { Text.loc(it, "en-US").ifEmpty { Text.loc(it, "ko-KR") } } ?: emptyList()
            tiers.isEmpty() || difficulty in tiers
        }
        return kept.ifEmpty { variants }
    }

    /** 只保留符合遊戲內日期的版本；沒有任何版本符合就全部保留。 */
    fun filterPhase(variants: List<JsonObject>, phase: Text.Phase?): Pair<List<JsonObject>, Boolean> {
        if (phase == null || variants.size <= 1) return variants to false
        val matched = variants.filter { v ->
            v["times"].arr()?.any { t ->
                val text = t.str() ?: Text.loc(t, "ko-KR").ifEmpty { Text.loc(t, "zh-TW") }
                Text.parsePhase(text) == phase
            } == true
        }
        return if (matched.isNotEmpty()) matched to true else variants to false
    }

    data class Candidate(val score: Double, val card: JsonObject, val event: JsonObject)

    /** 由高到低排列所有阿爾克那事件的名稱相似度。 */
    fun arcanaTitleCandidates(data: GameData, title: String): List<Candidate> =
        data.cards.flatMap { card -> card.objects("events").map { Candidate(variantScore(it, title), card, it) } }
            .sortedByDescending { it.score }

    fun bestEventInCard(card: JsonObject, title: String): Pair<JsonObject?, Double> {
        val events = card.objects("events")
        if (events.isEmpty()) return null to 0.0
        var best = 0
        var bestScore = variantScore(events[0], title)
        for (i in 1 until events.size) {
            val s = variantScore(events[i], title)
            if (s >= bestScore) {  // 同分時取後面的（與 Python max((分數, 索引)) 相同）
                best = i
                bestScore = s
            }
        }
        return events[best] to bestScore
    }
}
