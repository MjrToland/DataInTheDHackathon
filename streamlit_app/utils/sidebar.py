"""
Shared sidebar: user info, logout, and language selector.
Import and call render_sidebar(session) from every page.
"""
import streamlit as st

LANG_NAMES = {
    "en": "English",
    "es": "Español",
    "ar": "العربية",
    "zh": "中文",
    "fr": "Français",
    "pt": "Português",
    "de": "Deutsch",
    "ko": "한국어",
    "ja": "日本語"
}


def render_sidebar(session, show_language=False):
    role = st.session_state.get("role")

    st.sidebar.title("Drug Interaction Intelligence")
    st.sidebar.markdown("---")

    if role == "provider":
        st.sidebar.markdown(f"**Provider**")
        st.sidebar.markdown(st.session_state.get("provider_name", ""))
    elif role == "patient":
        st.sidebar.markdown(f"**Patient**")
        st.sidebar.markdown(st.session_state.get("patient_name", ""))
    elif role == "admin":
        st.sidebar.markdown("**Admin / Demo Mode**")

    if role:
        if st.sidebar.button("Log out"):
            for key in ["role", "provider_id", "provider_name", "patient_id",
                        "patient_name", "patient_lang", "suggested_patient", "messages"]:
                st.session_state.pop(key, None)
            st.experimental_rerun()

    lang = "en"
    if show_language:
        st.sidebar.markdown("---")
        default_lang = st.session_state.get("patient_lang", "en") if role == "patient" else "en"
        default_idx = list(LANG_NAMES.keys()).index(default_lang) if default_lang in LANG_NAMES else 0
        lang = st.sidebar.selectbox(
            "Language", list(LANG_NAMES.keys()),
            format_func=lambda x: LANG_NAMES[x],
            index=default_idx,
            key="sidebar_lang"
        )

    st.sidebar.markdown("---")

    if role == "provider":
        st.sidebar.markdown("""**Your Pages**
- Provider Dashboard
- Interaction Checker
- Chat
- Inbox Triage""")
    elif role == "patient":
        st.sidebar.markdown("""**Your Pages**
- Patient Portal
- Interaction Checker
- Chat""")

    st.sidebar.markdown("**DataInTheD Hackathon 2026**")

    return lang


def translate(text, lang, session):
    if not text or lang == "en":
        return text
    result = session.sql(
        "SELECT AI_TRANSLATE(?, 'en', ?) AS T",
        params=[str(text), lang]
    ).collect()
    return result[0]["T"] if result else text
