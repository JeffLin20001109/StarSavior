package com.starsavior.helper.core

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

/** 與 Windows 版（Python）的輸出逐字比對：shared/golden 由 desktop/tools/make_golden.py 產生。 */
class GoldenTest {
    private val shared = File(System.getProperty("shared.dir") ?: "../../shared")
    private fun load(name: String): JsonElement = parseJson(shared.resolve("golden/$name").readText())

    private fun boxes(array: JsonArray) = array.map {
        val o = it.jsonObject
        Box(o.getValue("text").jsonPrimitive.content, o.getValue("x0").jsonPrimitive.double, o.getValue("y0").jsonPrimitive.double,
            o.getValue("x1").jsonPrimitive.double, o.getValue("y1").jsonPrimitive.double)
    }

    /** 與 make_golden.py 的 lines_json 相同的格式。 */
    private fun linesJson(lines: List<Line>): List<Any?> = lines.map { line ->
        listOf(line.segments.map { listOf(it.text, it.style) },
            line.fold?.let { if (it.head) listOf("head", it.id, it.collapsed) else listOf("body", it.id) })
    }

    private fun expectedLines(array: JsonArray): List<Any?> = array.map { item ->
        val o = item.jsonObject
        val segments = o.getValue("segments").jsonArray.map { s -> s.jsonArray.map { it.jsonPrimitive.content } }
        val fold = (o["fold"] as? JsonArray)?.map { f ->
            val p = f.jsonPrimitive
            p.booleanOrNull?.takeIf { p.content == "true" || p.content == "false" } ?: if (p.isString) p.content else p.int
        }
        listOf(segments, fold)
    }

    private val prefixTranslator = TableTranslator(emptyMap(), fallback = { "譯:$it" })

    @Test
    fun textNormalizationAndSimilarity() {
        val cases = load("text_cases.json").jsonObject
        for (c in cases.getValue("norm").jsonArray.map { it.jsonObject }) {
            assertEquals(c.getValue("expected").jsonPrimitive.content, Text.norm(c.getValue("text").jsonPrimitive.content))
        }
        for (c in cases.getValue("similarity").jsonArray.map { it.jsonObject }) {
            val actual = Text.similarity(c.getValue("a").jsonPrimitive.content, c.getValue("b").jsonPrimitive.content)
            assertEquals(c.getValue("expected").jsonPrimitive.double, actual, 1e-6, c.toString())
        }
        for (c in cases.getValue("phase").jsonArray.map { it.jsonObject }) {
            val expected = c.getValue("expected")
            val actual = Text.parsePhase(c.getValue("text").jsonPrimitive.content)
            if (expected is JsonNull) assertNull(actual) else {
                assertEquals(expected.jsonArray[0].jsonPrimitive.int, actual?.month)
                assertEquals(expected.jsonArray[1].jsonPrimitive.content, actual?.part)
            }
        }
    }

    @Test
    fun eventDetectionOnRealScreenshots() {
        for (screen in load("screens.json").jsonArray.map { it.jsonObject }) {
            val expected = screen.getValue("expected").jsonObject
            val event = EventDetector.findEvent(boxes(screen.getValue("boxes").jsonArray))!!
            assertEquals(expected.getValue("kind").jsonPrimitive.content, event.kind.name.lowercase())
            assertEquals(expected.getValue("title").jsonPrimitive.content, event.title)
            assertEquals(expected.getValue("phase").jsonArray[0].jsonPrimitive.int, event.phase?.month)
            val crop = EventDetector.cardCrop(screen.getValue("width").jsonPrimitive.int, screen.getValue("height").jsonPrimitive.int, event.label)
            val size = expected.getValue("card_crop_size").jsonArray.map { it.jsonPrimitive.int }
            assertEquals(size, listOf(crop.width, crop.height))
        }
    }

    @Test
    fun fullPipelineMatchesDesktop() {
        val data = GameData(load("sample_data.json").jsonObject)
        val screens = load("screens.json").jsonArray.map { it.jsonObject }.associateBy { it.getValue("image").jsonPrimitive.content }
        for (case in load("pipeline_cases.json").jsonArray.map { it.jsonObject }) {
            val screen = case["image"]?.jsonPrimitive?.content?.let { screens.getValue(it) } ?: case
            val cardId = case["card_id"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.int
            val pipeline = Pipeline({ data }, { Renderer(it, prefixTranslator) })
            val result = pipeline.run(boxes(screen.getValue("boxes").jsonArray), screen.getValue("width").jsonPrimitive.int,
                screen.getValue("height").jsonPrimitive.int) { _, candidates ->
                CardMatch(candidates.firstOrNull { it["id"]?.jsonPrimitive?.int == cardId }?.takeIf { cardId != null }, emptyList(), 0)
            }
            val expected = case.getValue("expected").jsonObject
            assertEquals(expected.getValue("title").jsonPrimitive.content, result.title)
            assertEquals(expected.getValue("found").jsonPrimitive.content.toBoolean(), result.found)
            assertEquals(expectedLines(expected.getValue("lines").jsonArray), linesJson(result.lines), case["image"].toString())
        }
    }

    @Test
    fun realMultiVariantEventsRenderIdentically() {
        val multi = parseJson(shared.resolve("strings/multi_variants.json").readText()).jsonObject
        val data = GameData(mapOf("journeys" to multi, "arcanas" to JsonArray(emptyList()), "journey_items" to JsonArray(emptyList()),
            "potentials" to JsonArray(emptyList()), "stat_potentials" to JsonArray(emptyList()), "journey_buffs" to JsonArray(emptyList())))
        val table = TableTranslator.parseTable(shared.resolve("translations_zh.json").readText())
        val renderer = Renderer(data, TableTranslator(table))
        val cases = load("render_cases.json").jsonObject
        for (case in cases.getValue("render").jsonArray.map { it.jsonObject }) {
            val key = case.getValue("journey_key").jsonPrimitive.content
            val variants = multi.getValue(key).jsonArray.map { it.jsonObject }
            assertEquals(expectedLines(case.getValue("expected").jsonArray), linesJson(renderer.render(listOf(Section(variants)))), key)
        }
        for (case in cases.getValue("match").jsonArray.map { it.jsonObject }) {
            val phase = (case["phase"] as? JsonArray)?.let { Text.Phase(it[0].jsonPrimitive.int, it[1].jsonPrimitive.content) }
            val match = Matching.matchJourney(data, case.getValue("title").jsonPrimitive.content, phase, case.getValue("difficulty").jsonPrimitive.content)
            assertEquals(case.getValue("expected_ids").jsonArray.map { it.jsonPrimitive.int }, match.variants.map { it.getValue("id").jsonPrimitive.int })
            assertEquals(case.getValue("expected_score").jsonPrimitive.double, match.score, 1e-6)
        }
    }

    @Suppress("unused")
    private fun JsonObject.prim(key: String) = this[key] as? JsonPrimitive
}
