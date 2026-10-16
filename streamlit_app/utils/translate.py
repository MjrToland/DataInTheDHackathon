"""
Utility: Translation wrapper using Snowflake CORTEX.TRANSLATE.
"""
from snowflake.snowpark.context import get_active_session

SUPPORTED_LANGUAGES = {
    "en": "English", "es": "Spanish", "ar": "Arabic", "zh": "Chinese",
    "fr": "French", "pt": "Portuguese", "de": "German", "ko": "Korean",
    "vi": "Vietnamese", "ja": "Japanese"
}


def translate_text(text: str, target_lang: str, source_lang: str = "en", session=None) -> str:
    """Translate text using Snowflake Cortex TRANSLATE."""
    if not text or target_lang == source_lang:
        return text

    if session is None:
        session = get_active_session()

    safe_text = text.replace("$$", "$ $")
    result = session.sql(f"""
        SELECT SNOWFLAKE.CORTEX.TRANSLATE($${safe_text}$$, '{source_lang}', '{target_lang}') AS TRANSLATED
    """).collect()

    return result[0]["TRANSLATED"] if result else text
