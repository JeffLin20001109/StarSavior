package com.starsavior.helper.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull

/** 網站 JSON 的存取小工具；語意比照 Windows 版 Python（dict.get、真值判斷）。 */
internal val json = Json { ignoreUnknownKeys = true }

fun parseJson(text: String): JsonElement = json.parseToJsonElement(text)

internal fun JsonElement?.obj(): JsonObject? = this as? JsonObject
internal fun JsonElement?.arr(): JsonArray? = this as? JsonArray

internal fun JsonElement?.str(): String? = (this as? JsonPrimitive)?.takeIf { it.isString }?.content

/** 數字（不含字串、布林）。 */
internal fun JsonElement?.num(): Double? {
    val p = this as? JsonPrimitive ?: return null
    if (p.isString || p is JsonNull || p.content == "true" || p.content == "false") return null
    return p.doubleOrNull
}

/** 陣列中的物件（略過其他型別），對應 Python 的 [c for c in v.get(key) or [] if isinstance(c, dict)]。 */
internal fun JsonObject.objects(key: String): List<JsonObject> = this[key].arr()?.mapNotNull { it.obj() } ?: emptyList()

/** Python 的真值：None、空字串、空陣列、空物件、0 都是 false。 */
internal fun truthy(e: JsonElement?): Boolean = when (e) {
    null, JsonNull -> false
    is JsonObject -> e.isNotEmpty()
    is JsonArray -> e.isNotEmpty()
    is JsonPrimitive -> if (e.isString) e.content.isNotEmpty() else e.content != "false" && e.num() != 0.0
}

/** Python 的 f'{value}'：數字依原樣、字串原文、缺少時為預設值、null 為 None。 */
internal fun pyStr(e: JsonElement?, default: String = ""): String = when (e) {
    null -> default
    JsonNull -> "None"
    is JsonPrimitive -> when (e.content) {
        "true" -> if (e.isString) "true" else "True"
        "false" -> if (e.isString) "false" else "False"
        else -> e.content
    }
    else -> e.toString()
}

/** 排序鍵的 JSON 字串，用來判斷兩筆資料是否相同（比照 json.dumps(sort_keys=True)）。 */
internal fun canonical(e: JsonElement?): String = when (e) {
    null, JsonNull -> "null"
    is JsonPrimitive -> e.toString()
    is JsonArray -> e.joinToString(",", "[", "]") { canonical(it) }
    is JsonObject -> e.keys.sorted().joinToString(",", "{", "}") { JsonPrimitive(it).toString() + ":" + canonical(e[it]) }
}
