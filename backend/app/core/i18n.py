SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh": "简体中文",
    "ms": "Bahasa Melayu",
}

LANGUAGE_ALIASES = {
    "en-us": "en",
    "en-gb": "en",
    "english": "en",
    "zh-cn": "zh",
    "zh-hans": "zh",
    "cn": "zh",
    "chinese": "zh",
    "中文": "zh",
    "ms-my": "ms",
    "malay": "ms",
    "bahasa": "ms",
    "bahasa melayu": "ms",
}

LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Simplified Chinese",
    "ms": "Malay",
}


def normalize_language(value: str | None) -> str:
    if not value:
        return "en"
    candidate = value.strip().lower().split(",")[0]
    candidate = candidate.split(";")[0]
    if candidate in SUPPORTED_LANGUAGES:
        return candidate
    return LANGUAGE_ALIASES.get(candidate, "en")


def language_choices() -> list[dict[str, str]]:
    return [{"code": code, "label": label} for code, label in SUPPORTED_LANGUAGES.items()]


def answer_language_instruction(language: str) -> str:
    name = LANGUAGE_NAMES.get(normalize_language(language), "English")
    return f"Write all user-facing analysis text in {name}."


def fallback_summary(language: str, question: str, row_count: int, chart_created: bool) -> str:
    lang = normalize_language(language)
    if lang == "zh":
        chart_text = "已生成图表。" if chart_created else "没有生成图表。"
        return f"分析已完成。问题：{question}。结果表包含 {row_count} 行。{chart_text}"
    if lang == "ms":
        chart_text = "Carta telah dijana." if chart_created else "Tiada carta dijana."
        return f"Analisis selesai. Soalan: {question}. Jadual hasil mengandungi {row_count} baris. {chart_text}"
    chart_text = "A chart was generated." if chart_created else "No chart was generated."
    return f"Analysis completed. Question: {question}. The result table contains {row_count} rows. {chart_text}"

