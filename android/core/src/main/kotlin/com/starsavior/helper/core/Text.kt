package com.starsavior.helper.core

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 文字處理：取出多語系欄位、正規化比對用字串、相似度（移植自 desktop/journey_helper/text.py）。 */
object Text {
    private val TAG = Regex("<[^>]+>")
    private val ENTITY = Regex("&(#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z]+);")
    private val NAMED = mapOf("amp" to "&", "lt" to "<", "gt" to ">", "quot" to "\"", "apos" to "'", "nbsp" to " ")

    /** 繁→簡逐字對照（shared/t2s.json）。 */
    private val T2S: Map<Int, String> by lazy {
        val stream = Text::class.java.getResourceAsStream("t2s.json") ?: return@lazy emptyMap()
        val obj = parseJson(stream.bufferedReader(Charsets.UTF_8).readText()).jsonObject
        obj.entries.associate { (k, v) -> k.codePointAt(0) to v.jsonPrimitive.content }
    }

    fun clean(text: String): String = unescape(TAG.replace(text, "")).trim { it.isWhitespace() }

    private fun unescape(text: String): String = ENTITY.replace(text) { m ->
        val body = m.groupValues[1]
        when {
            body.startsWith("#x") || body.startsWith("#X") -> body.substring(2).toIntOrNull(16)?.let { String(Character.toChars(it)) }
            body.startsWith("#") -> body.substring(1).toIntOrNull()?.let { String(Character.toChars(it)) }
            else -> NAMED[body]
        } ?: m.value
    }

    /** 取出多語系欄位 {"zh-TW": ..., "ko-KR": ...} 的指定語言；字串直接回傳。 */
    fun loc(value: JsonElement?, lang: String): String = when (value) {
        is JsonPrimitive -> if (value.isString) clean(value.content) else ""
        is JsonObject -> value[lang].str()?.let { clean(it) } ?: ""
        else -> ""
    }

    fun t2s(text: String): String {
        val out = StringBuilder()
        var i = 0
        while (i < text.length) {
            val cp = text.codePointAt(i)
            out.append(T2S[cp] ?: String(Character.toChars(cp)))
            i += Character.charCount(cp)
        }
        return out.toString()
    }

    /** Python re 的 \w：字母（L*）、數字（Nd、Nl、No）；底線另外排除。 */
    private fun isWord(cp: Int): Boolean = when (Character.getType(cp)) {
        Character.UPPERCASE_LETTER.toInt(), Character.LOWERCASE_LETTER.toInt(), Character.TITLECASE_LETTER.toInt(),
        Character.MODIFIER_LETTER.toInt(), Character.OTHER_LETTER.toInt(),
        Character.DECIMAL_DIGIT_NUMBER.toInt(), Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> true
        else -> false
    }

    /** 比對用：繁轉簡、去除空白與標點、轉小寫。 */
    fun norm(text: String?): String {
        val converted = t2s(text ?: "")
        val out = StringBuilder()
        var i = 0
        while (i < converted.length) {
            val cp = converted.codePointAt(i)
            if (isWord(cp)) out.appendCodePoint(cp)
            i += Character.charCount(cp)
        }
        return out.toString().lowercase()
    }

    fun similarity(a: String, b: String): Double {
        val x = norm(a)
        val y = norm(b)
        if (x.isEmpty() || y.isEmpty()) return 0.0
        var ratio = SequenceMatcher.ratio(x, y)
        val shorter = minOf(x.codePointCount(0, x.length), y.codePointCount(0, y.length))
        val longer = maxOf(x.codePointCount(0, x.length), y.codePointCount(0, y.length))
        if (shorter >= 3 && (y.contains(x) || x.contains(y))) {
            ratio = maxOf(ratio, 0.85 * shorter / longer + 0.15)
        }
        return ratio
    }

    data class Phase(val month: Int, val part: String)

    private val PHASE = Regex("(\\d{1,2})\\s*[월月]\\s*(초순|상순|중순|하순|上旬|初旬|中旬|下旬)")
    private val PART = mapOf(
        "초순" to "early", "상순" to "early", "중순" to "mid", "하순" to "late",
        "上旬" to "early", "初旬" to "early", "中旬" to "mid", "下旬" to "late",
    )
    private val PART_ZH = mapOf("early" to "上旬", "mid" to "中旬", "late" to "下旬")

    /** '3월 초순' 或 '3月上旬' → Phase(3, "early")；無法解析回傳 null。 */
    fun parsePhase(text: String?): Phase? {
        val m = PHASE.find(text ?: return null) ?: return null
        val month = m.groupValues[1].toInt()
        if (month !in 1..12) return null
        return Phase(month, PART.getValue(m.groupValues[2]))
    }

    fun phaseZh(text: String?): String? = parsePhase(text)?.let { "${it.month}月${PART_ZH.getValue(it.part)}" }
}

/** Python difflib.SequenceMatcher（無 junk）的 ratio()，以 code point 為單位。 */
internal object SequenceMatcher {
    fun ratio(a: String, b: String): Double {
        val x = a.codePoints().toArray()
        val y = b.codePoints().toArray()
        val total = x.size + y.size
        if (total == 0) return 1.0
        return 2.0 * matches(x, y) / total
    }

    private fun matches(a: IntArray, b: IntArray): Int {
        val b2j = HashMap<Int, MutableList<Int>>()
        b.forEachIndexed { j, c -> b2j.getOrPut(c) { mutableListOf() }.add(j) }
        var total = 0
        val queue = ArrayDeque<IntArray>()
        queue.addLast(intArrayOf(0, a.size, 0, b.size))
        while (queue.isNotEmpty()) {
            val (alo, ahi, blo, bhi) = queue.removeLast()
            val (i, j, k) = longest(a, b2j, alo, ahi, blo, bhi)
            if (k > 0) {
                total += k
                if (alo < i && blo < j) queue.addLast(intArrayOf(alo, i, blo, j))
                if (i + k < ahi && j + k < bhi) queue.addLast(intArrayOf(i + k, ahi, j + k, bhi))
            }
        }
        return total
    }

    private fun longest(a: IntArray, b2j: Map<Int, List<Int>>, alo: Int, ahi: Int, blo: Int, bhi: Int): Triple<Int, Int, Int> {
        var bestI = alo
        var bestJ = blo
        var bestSize = 0
        var j2len = HashMap<Int, Int>()
        for (i in alo until ahi) {
            val next = HashMap<Int, Int>()
            for (j in b2j[a[i]] ?: emptyList()) {
                if (j < blo) continue
                if (j >= bhi) break
                val k = (j2len[j - 1] ?: 0) + 1
                next[j] = k
                if (k > bestSize) {
                    bestI = i - k + 1
                    bestJ = j - k + 1
                    bestSize = k
                }
            }
            j2len = next
        }
        return Triple(bestI, bestJ, bestSize)
    }
}
