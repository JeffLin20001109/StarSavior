package com.starsavior.helper.core

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** 網站 star-savior-arcana-db 的公開 JSON（移植自 desktop/journey_helper/data.py）。 */
class GameData(raw: Map<String, JsonElement>) {
    val journeyGroups: List<List<JsonObject>>
    val cards: List<JsonObject>
    private val references: Map<String, Map<String, JsonObject>>

    init {
        val missing = FILES.filter { it !in raw }
        require(missing.isEmpty()) { "資料不完整：" + missing.joinToString(", ") }
        journeyGroups = when (val journeys = raw.getValue("journeys")) {
            is JsonObject -> journeys.values.mapNotNull { (it as? JsonArray)?.mapNotNull { v -> v.obj() } }
            is JsonArray -> journeys.mapNotNull { it.obj()?.let { v -> listOf(v) } }
            else -> emptyList()
        }
        val arcanas = raw.getValue("arcanas")
        require(journeyGroups.isNotEmpty() && arcanas is JsonArray) { "旅程或阿爾克那資料格式不正確" }
        cards = arcanas.mapNotNull { it.obj() }
        references = FILES.drop(2).associateWith { name ->
            (raw[name] as? JsonArray)?.mapNotNull { it.obj() }?.associateBy { pyStr(it["id"], "None") } ?: emptyMap()
        }
    }

    fun reference(type: String, id: JsonElement?): JsonObject? {
        val table = REFERENCE_TYPES[type] ?: return null
        return references[table]?.get(pyStr(id, "None"))
    }

    fun journeyCount(): Int = journeyGroups.sumOf { it.size }

    fun cardName(card: JsonObject): String =
        Text.loc(card["name"], "zh-TW").ifEmpty { Text.loc(card["name"], "ko-KR") }

    companion object {
        val FILES = listOf("journeys", "arcanas", "journey_items", "potentials", "stat_potentials", "journey_buffs")
        val REFERENCE_TYPES = mapOf(
            "RT_JOURNEY_ITEM" to "journey_items",
            "RT_SE_POTEN" to "potentials",
            "RT_STAT_POTEN" to "stat_potentials",
            "RT_JOURNEY_BUFF" to "journey_buffs",
        )

        /** 從 {檔名: JSON 文字} 建立。 */
        fun fromTexts(texts: Map<String, String>): GameData = GameData(texts.mapValues { parseJson(it.value) })

        @Suppress("unused")
        internal fun primitive(value: String) = JsonPrimitive(value)
    }
}
