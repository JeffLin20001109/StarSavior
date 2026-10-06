package com.starsavior.helper.core

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import java.math.BigDecimal
import java.math.MathContext

/**
 * 把網站的韓文事件資料整理成小窗要顯示的繁中文字（移植自 desktop/journey_helper/render.py）。
 *
 * 樣式：h1 事件名、h2 區段、choice 選項、effect 效果、note 附註、warn 警告、dim 說明、
 * special 基本能力以外的獎勵（道具、潛力、旅程效果等）、minus 扣減的項目。
 */
data class Segment(val text: String, val style: String)

/** fold：摺疊標題（head=true，collapsed 為預設是否收起）或摺疊內容（head=false）。 */
data class Fold(val head: Boolean, val id: Int, val collapsed: Boolean = false)

data class Line(val segments: List<Segment>, val fold: Fold? = null) {
    constructor(text: String, style: String) : this(listOf(Segment(text, style)))

    val text: String get() = segments.joinToString("") { it.text }
}

data class Section(val variants: List<JsonObject>, val heading: String? = null)

class Renderer(
    private val data: GameData,
    val translator: Translator,
    private val terms: Map<String, String> = Terms.DEFAULT,
) {
    private var foldCount = 0
    private var tr: (String) -> String = { it }

    fun render(sections: List<Section>): List<Line> {
        val recorded = ArrayList<String>()
        tr = { ko -> recorded.add(ko); ko }
        foldCount = 0
        lines(sections)
        val mapping = translator.translateMany(recorded)
        tr = { ko -> mapping[ko] ?: ko }
        foldCount = 0
        val result = lines(sections).toMutableList()
        if (translator.failed) {
            val reason = translator.lastError
            result.add(0, Line("部分文字無法連線翻譯，暫時顯示韓文原文；下次點擊會自動重新翻譯。" +
                (if (reason != null) "（$reason）" else ""), "warn"))
        }
        return result
    }

    private fun ko(value: JsonElement?) = Text.loc(value, "ko-KR")

    private fun lines(sections: List<Section>): List<Line> {
        val out = ArrayList<Line>()
        val blank = Line("", "dim")
        for (section in sections) {
            section.heading?.takeIf { it.isNotEmpty() }?.let { out.add(Line(it, "h2")) }
            for (group in grouped(distinct(section.variants))) out.addAll(event(group))
            out.add(blank)
        }
        while (out.isNotEmpty() && out.last() == blank) out.removeAt(out.size - 1)
        return out
    }

    private fun distinct(variants: List<JsonObject>): List<JsonObject> {
        val seen = HashSet<String>()
        return variants.filter { v ->
            seen.add(listOf("name", "choices", "times", "difficulties", "battle_names").joinToString("|") { canonical(v[it]) })
        }
    }

    /** 同名、選項也相同的事件版本合併成一個區塊。 */
    private fun grouped(variants: List<JsonObject>): List<List<JsonObject>> {
        val groups = LinkedHashMap<String, MutableList<JsonObject>>()
        for (v in variants) {
            val key = canonical(v["name"]) + "|" + v.objects("choices").joinToString(",") { canonical(it["name"]) }
            groups.getOrPut(key) { mutableListOf() }.add(v)
        }
        return groups.values.toList()
    }

    private fun difficulties(v: JsonObject): List<String> = (v["difficulties"].arr() ?: emptyList()).map { d ->
        val en = Text.loc(d, "en-US")
        DIFFICULTY_ZH[en] ?: tr(ko(d)).ifEmpty { en }
    }.filter { it.isNotEmpty() }

    private fun battles(v: JsonObject): List<String> =
        (v["battle_names"].arr() ?: emptyList()).filter { ko(it).isNotEmpty() }.map { tr(ko(it)) }

    private fun timeText(t: JsonElement): String {
        val raw = t.str() ?: ko(t).ifEmpty { Text.loc(t, "en-US") }
        return Text.phaseZh(raw) ?: raw
    }

    private fun times(v: JsonObject): List<String> = (v["times"].arr() ?: emptyList()).map { timeText(it) }.filter { it.isNotEmpty() }

    /** 每個版本的標籤：依日期、難度或戰鬥區分；資料沒有說明條件時標為「可能結果 n」。 */
    private fun labels(group: List<JsonObject>): Pair<List<String>, Boolean> {
        if (group.size == 1) return listOf("") to false
        val parts = List(group.size) { ArrayList<String>() }
        for (getter in listOf(::times, ::difficulties, ::battles)) {
            val values = group.map { getter(it) }
            if (values.toSet().size > 1) {
                parts.zip(values).forEach { (part, value) -> part.add(value.joinToString("、").ifEmpty { "其他" }) }
            }
        }
        var labels = parts.map { it.joinToString("｜") }
        if (labels.all { it.isEmpty() }) return List(group.size) { "可能結果 ${it + 1}" } to true
        if (labels.toSet().size < labels.size) labels = labels.mapIndexed { i, label -> "$label ${i + 1}" }
        return labels to false
    }

    private fun event(group: List<JsonObject>): List<Line> {
        val out = ArrayList<Line>()
        val first = group[0]
        val name = ko(first["name"]).ifEmpty { Text.loc(first["name"], "en-US") }.ifEmpty { "（未命名事件）" }
        out.add(Line(tr(name), "h1"))
        val context = ArrayList<String>()
        for (v in group) for (t in v["times"].arr() ?: emptyList()) context.add(timeText(t))
        if (group.map { difficulties(it) }.toSet().size == 1) context.addAll(difficulties(first))
        if (group.map { battles(it) }.toSet().size == 1) context.addAll(battles(first))
        val shownContext = context.distinct().filter { it.isNotEmpty() }
        if (shownContext.isNotEmpty()) out.add(Line("［" + shownContext.joinToString(" | ") + "］", "note"))
        val (labels, uncertain) = labels(group)
        val diffs = group.map { difficulties(it) }
        val byDifficulty = diffs.toSet().size > 1
        val isHard = diffs.map { DIFFICULTY_ZH.getValue("Hard") in it }
        if (uncertain) out.add(Line("網站列出 ${group.size} 種可能結果，遊戲中會出現其中一種（資料沒有說明條件）。", "dim"))
        val choices = first.objects("choices")
        if (choices.isEmpty()) out.add(Line("（沒有效果資料）", "dim"))
        val details = group.size <= 8
        choices.forEachIndexed { i, choice ->
            val mark = if (i < CIRCLED.length) CIRCLED[i].toString() else "${i + 1}."
            val choiceName = ko(choice["name"])
            out.add(if (choiceName.isNotEmpty()) Line("$mark " + tr(choiceName), "choice") else Line("（無選項，自動發生）", "choice"))
            val perVariant = group.map { choiceOf(it, i) }
            val sharedCondition = perVariant.map { canonical(it["condition"]) }.toSet().size == 1
            if (sharedCondition && truthy(choice["condition"])) {
                out.add(Line("　條件／消耗：" + condition(choice["condition"].obj()!!), "warn"))
            }
            // 結果相同的版本合併，保留第一次出現的順序
            val outcomes = LinkedHashMap<String, Triple<MutableList<String>, List<Line>, MutableList<Boolean>>>()
            for (index in group.indices) {
                val body = outcome(perVariant[index], !sharedCondition, details)
                val key = body.joinToString("\n") { line -> line.segments.joinToString("\u0001") { it.text + "\u0002" + it.style } }
                val entry = outcomes.getOrPut(key) { Triple(mutableListOf(), body, mutableListOf()) }
                entry.first.add(labels[index])
                entry.third.add(isHard[index])
            }
            if (outcomes.size == 1) {
                out.addAll(outcomes.values.first().second)
                return@forEachIndexed
            }
            for ((names, body, hards) in outcomes.values) {
                val header = "〔" + names.joinToString("／") + "〕"
                val indented = body.map { line ->
                    Line(listOf(Segment("　" + line.segments[0].text, line.segments[0].style)) + line.segments.drop(1))
                }
                if (!byDifficulty) {
                    out.add(Line("　$header", "note"))
                    out.addAll(indented)
                    continue
                }
                // 依難度不同的結果：困難以外預設摺疊，點標題可展開
                val collapsed = hards.none { it }
                val fold = ++foldCount
                out.add(Line(listOf(Segment("　" + (if (collapsed) "▶ " else "▼ ") + header, "note")), Fold(true, fold, collapsed)))
                indented.forEach { out.add(it.copy(fold = Fold(false, fold))) }
            }
        }
        return out
    }

    private fun choiceOf(variant: JsonObject, index: Int): JsonObject =
        variant.objects("choices").getOrNull(index) ?: JsonObject(emptyMap())

    private fun outcome(choice: JsonObject, withCondition: Boolean, details: Boolean): List<Line> {
        val out = ArrayList<Line>()
        if (withCondition && truthy(choice["condition"])) out.add(Line("　條件／消耗：" + condition(choice["condition"].obj()!!), "warn"))
        val failure = choice["failure_rewards"]
        if (truthy(failure)) out.add(Line("　成功時：", "note"))
        out.addAll(groups(choice["success_rewards"], details))
        if (truthy(failure)) {
            out.add(Line("　失敗時：", "warn"))
            out.addAll(groups(failure, details))
        }
        return out
    }

    private fun groups(groups: JsonElement?, showDetails: Boolean): List<Line> {
        val none = listOf(Line("　・無效果", "effect"))
        val list = groups.arr()
        if (list == null || list.isEmpty()) return none
        val out = ArrayList<Line>()
        for (group in list) {
            val entries = group.arr()?.toList() ?: listOf(group)
            val segments = ArrayList<Segment>()
            val descriptions = ArrayList<String>()
            for (entry in entries.mapNotNull { it.obj() }) {
                val (label, detail) = reward(entry)
                if (segments.isNotEmpty()) segments.add(Segment(" 或 ", "effect"))
                segments.add(Segment(label, rewardStyle(entry)))
                descriptions.addAll(detail)
            }
            if (segments.isNotEmpty()) {
                out.add(Line(listOf(Segment("　・", "effect")) + segments))
                if (showDetails) descriptions.forEach { out.add(Line("　　$it", "dim")) }
            }
        }
        return out.ifEmpty { none }
    }

    private fun rewardStyle(entry: JsonObject): String {
        val low = entry["min"]
        val high = if ("max" in entry) entry["max"] else entry["min"]
        if (listOf(low, high).any { (it.num() ?: 0.0) < 0 }) return "minus"
        return if (pyStr(entry["type"], "") in BASIC_TYPES) "effect" else "special"
    }

    private fun reward(entry: JsonObject): Pair<String, List<String>> {
        val kind = pyStr(entry["type"], "")
        val details = ArrayList<String>()
        var label: String
        if (kind in GameData.REFERENCE_TYPES) {
            val ref = data.reference(kind, entry["reward_id"]) ?: JsonObject(emptyMap())
            val name = ko(ref["name"])
            label = if (name.isNotEmpty()) tr(name) else Text.loc(ref["name"], "en-US").ifEmpty { "#" + pyStr(entry["reward_id"], "None") }
            if (kind == "RT_JOURNEY_BUFF") label = "旅程效果「$label」"
            val desc = ko(if (truthy(ref["desc"])) ref["desc"] else ref["description"])
            if (desc.isNotEmpty()) details.add(tr(desc))
        } else if (kind == "RT_STAT") {
            val stat = pyStr(entry["reward_stat"], "").removePrefix("JST_")
            label = terms[stat] ?: stat
        } else {
            label = terms[kind] ?: kind.ifEmpty { "?" }
        }
        label += amount(entry)
        for (key in listOf("turn", "turns", "duration")) {
            val turns = entry[key].num() ?: continue
            label += "（${fmt(turns)} 回合）"
            break
        }
        return label to details
    }

    private fun amount(entry: JsonObject): String {
        if ("min" !in entry || pyStr(entry["type"], "") == "RT_STAT_POTEN") return ""
        val low = entry["min"].num() ?: return ""
        val high = (if ("max" in entry) entry["max"] else entry["min"]).num() ?: return ""
        return if (low == high) " " + signed(low) else " " + signed(low) + "~" + signed(high)
    }

    private fun condition(entry: JsonObject): String {
        val kind = pyStr(entry["type"], "")
        val value = pyStr(entry["value"], "")
        val names = mapOf("RR_STAMINA_USE" to "RT_STAMINA", "RR_COIN_USE" to "RT_COIN", "RR_PP_USE" to "RT_POTEN_POINT")
        names[kind]?.let { return "${terms[it] ?: it} -$value" }
        if (kind == "RR_ITEM_USE" || kind == "RR_ITEM_CHECK") {
            val ref = data.reference("RT_JOURNEY_ITEM", entry["target"]) ?: JsonObject(emptyMap())
            val name = if (ko(ref["name"]).isNotEmpty()) tr(ko(ref["name"])) else "道具 #" + pyStr(entry["target"], "None")
            return if (kind == "RR_ITEM_CHECK") "持有 $name ≥ $value" else "消耗 $name $value"
        }
        if (kind == "RR_STAT") {
            val stat = pyStr(entry["target"], "").removePrefix("JST_")
            return "${terms[stat] ?: stat} ≥ $value"
        }
        return "$kind $value".trim()
    }

    companion object {
        val DIFFICULTY_ZH = mapOf("Easy" to "簡單", "Normal" to "普通", "Hard" to "困難")
        const val CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"

        /** 基本能力與資源用一般顏色；其他獎勵（道具、潛力、旅程效果、遺物…）用暗黃色。 */
        val BASIC_TYPES = setOf("RT_STAT", "RT_STAMINA", "RT_CONDITION", "RT_COIN", "RT_POTEN_POINT", "RT_ARCANA_POINT")

        /** Python 的 f'{x:g}'。 */
        fun fmt(value: Double): String = BigDecimal(value).round(MathContext(6)).stripTrailingZeros().toPlainString()

        /** Python 的 f'{x:+g}'。 */
        fun signed(value: Double): String = (if (value >= 0) "+" else "") + fmt(value)
    }
}
