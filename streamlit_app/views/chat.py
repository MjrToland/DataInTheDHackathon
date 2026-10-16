"""Chat view — compatible with older SiS Streamlit (no chat_input/chat_message)."""
import json
import requests
import streamlit as st
from utils.sidebar import translate, LANG_NAMES


def call_agent_rest(prompt_text, session):
    try:
        conn = session.connection
        token = conn.rest.token
        scheme = conn.rest._protocol
        host = conn.rest._host
        port = conn.rest._port
        base_url = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"
        url = f"{base_url}/api/v2/databases/HEALTHCARE_DW/schemas/DDI_APP/agents/DRUG_INTERACTION_AGENT:run"
        headers = {"Authorization": f"Snowflake Token=\"{token}\"", "Content-Type": "application/json", "Accept": "application/json"}
        body = {"messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}], "stream": False}
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    return item.get("text", "")
            return json.dumps(data, indent=2)
    except Exception:
        pass
    return None


def call_search_fallback(prompt_text, session, role, lang):
    search_results = session.sql(
        """SELECT DRUG_A_NAME, DRUG_B_NAME, SEVERITY, CLINICAL_EFFECT, MANAGEMENT, ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
           FROM TABLE(HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_SEARCH!SEARCH(QUERY => ?, LIMIT => 5))""",
        params=[prompt_text]
    ).to_pandas()
    if not search_results.empty:
        ctx = "\n".join(f"- {r['DRUG_A_NAME']} + {r['DRUG_B_NAME']} ({r['SEVERITY']}): {r['CLINICAL_EFFECT']}. Management: {r['MANAGEMENT']}" for _, r in search_results.iterrows())
    else:
        ctx = "No specific drug interaction data found."
    persona = "You are speaking to a patient. Use plain language." if role == "patient" else "You are speaking to a healthcare provider. Use clinical terminology."
    lang_inst = f" Respond entirely in {LANG_NAMES.get(lang, lang)}." if lang != "en" else ""
    safe_p = prompt_text.replace("$$", "$ $")
    safe_c = ctx.replace("$$", "$ $")
    result = session.sql(
        f"""SELECT AI_COMPLETE('claude-sonnet-4-6', CONCAT(
            'You are a clinical pharmacist AI assistant. ', $${persona}$$, ' ',
            'Answer based on the data below. Cite severity levels. All data is AI-generated, not clinically validated.',
            $${lang_inst}$$, CHR(10), CHR(10), 'DATA:', CHR(10), $${safe_c}$$,
            CHR(10), CHR(10), 'QUESTION: ', $${safe_p}$$
        ), OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 800)) AS RESPONSE"""
    ).collect()
    return result[0]["RESPONSE"] if result else "No response received."


def render(session, lang):
    role = st.session_state.get("role")
    st.title(translate("Medication Chat", lang, session))
    st.markdown(translate("Ask questions about drug interactions, medications, and patient safety.", lang, session))
    st.caption(translate("All answers are AI-generated and not clinically validated.", lang, session))

    # Chat history display
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**Assistant:** {msg['content']}")
            st.markdown("---")

    # Input form (works on all Streamlit versions)
    with st.form("chat_form", clear_on_submit=True):
        prompt = st.text_area(
            translate("Ask about medications, interactions, or patients...", lang, session),
            height=80, key="chat_input_area"
        )
        submitted = st.form_submit_button(translate("Send", lang, session), type="primary")

    if submitted and prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f"**You:** {prompt}")

        with st.spinner(translate("Thinking...", lang, session)):
            try:
                answer = call_agent_rest(prompt, session)
                if not answer:
                    answer = call_search_fallback(prompt, session, role, lang)
                if lang != "en" and answer:
                    answer = translate(answer, lang, session)
                st.markdown(f"**Assistant:** {answer}")
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Error: {str(e)}")
