package com.starsavior.helper.core

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 韓文 → 繁中。 */
interface Translator {
    fun translateMany(texts: List<String>): Map<String, String>
    val failed: Boolean get() = false
    val lastError: String? get() = null
}

/**
 * 翻譯優先順序：使用者自訂 → 人工校對譯文表 → 機器翻譯（fallback，可為 null）。
 * fallback 失敗時保留韓文。對應 desktop/journey_helper/translate.py。
 */
class TableTranslator(
    @Volatile var table: Map<String, String>,
    private val glossary: Map<String, String> = emptyMap(),
    private val replacements: Map<String, String> = emptyMap(),
    private val fallback: ((String) -> String)? = null,
) : Translator {
    @Volatile override var failed: Boolean = false
        private set
    @Volatile override var lastError: String? = null
        private set
    private val cache = java.util.concurrent.ConcurrentHashMap<String, String>()

    private fun post(text: String): String = replacements.entries.fold(text) { acc, (wrong, right) -> acc.replace(wrong, right) }

    override fun translateMany(texts: List<String>): Map<String, String> {
        failed = false
        val result = LinkedHashMap<String, String>()
        for (text in texts.filter { it.isNotEmpty() }.distinct()) {
            result[text] = when {
                text in glossary -> glossary.getValue(text)
                text in table -> post(table.getValue(text))
                cache.containsKey(text) -> post(cache.getValue(text))
                fallback != null -> try {
                    fallback.invoke(text).takeIf { it.isNotBlank() }?.also { cache[text] = it }?.let { post(it) } ?: run {
                        failed = true
                        lastError = "空白結果"
                        text
                    }
                } catch (e: Exception) {
                    failed = true
                    lastError = "${e.javaClass.simpleName}: ${e.message}"
                    text
                }
                else -> text
            }
        }
        return result
    }

    companion object {
        /** 解析譯文表：接受 {韓文: 中文} 或 {"translations": {...}}。 */
        fun parseTable(text: String): Map<String, String> {
            var obj = parseJson(text).obj() ?: return emptyMap()
            obj["translations"].obj()?.let { obj = it }
            return obj.entries.mapNotNull { (k, v) -> v.str()?.takeIf { it.isNotBlank() }?.let { k to it } }.toMap()
        }

        @Suppress("unused")
        private fun keys(obj: JsonObject) = obj.mapValues { it.value.jsonPrimitive.content }
    }
}

/** 遊戲固定用語（與 Windows 版 config.DEFAULTS["terms"] 相同）。 */
object Terms {
    val DEFAULT: Map<String, String> = mapOf(
        "POWER" to "力量", "HEALTH" to "體力", "ENDURANCE" to "韌性", "FOCUS" to "專注", "PROTECT" to "保護",
        "RT_STAMINA" to "耐力", "RT_COIN" to "古幣", "RT_CONDITION" to "狀態",
        "RT_POTEN_POINT" to "潛力點數", "RT_ARCANA_POINT" to "羈絆點數",
        "SELECTABLE_CHARM" to "可選擇的遺物",
        "RT_JOURNEY_BUFF_REMOVE_NEG" to "解除負面旅程效果",
        "RT_JOURNEY_BUFF_REMOVE_POS" to "解除正面旅程效果",
    )
}
