"""
Chat Interface — Conversational Q&A backed by the Cortex Agent.
Calls the agent REST API directly from Python, bypassing DATA_AGENT_RUN.
Falls back to Cortex Search + AI_COMPLETE if the agent call fails.
"""
import json
import requests
import streamlit as st
from snowflake.snowpark.context import get_active_session
from utils.sidebar import render_sidebar, translate, LANG_NAMES, require_login

st.set_page_config(page_title="Medication Chat", page_icon="💬", layout="wide")
session = get_active_session()
lang = render_sidebar(session, show_language=True)
require_login()
role = st.session_state.get("role")

st.title(translate("Medication Chat", lang, session))
st.markdown(translate("Ask questions about drug interactions, medications, and patient safety.", lang, session))
st.caption(translate("All answers are AI-generated and not clinically validated. Always consult a provider.", lang, session))

AGENT_FQN = "HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_AGENT"


def call_agent_rest(prompt_text, session):
    try:
        conn = session.connection
        token = conn.rest.token
        scheme = conn.rest._protocol
        host = conn.rest._host
        port = conn.rest._port
        base_url = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"

        url = f"{base_url}/api/v2/databases/HEALTHCARE_DW/schemas/DDI_APP/agents/DRUG_INTERACTION_AGENT:run"
        headers = {
            "Authorization": f"Snowflake Token=\"{token}\"",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Snowflake-Role": "ACCOUNTADMIN",
        }
        body = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
            ],
            "stream": False,
        }
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            # Extract text from the response
            for item in data.get("content", data.get("choices", [])):
                if isinstance(item, dict) and item.get("type") == "text":
                    return item.get("text", "")
                if isinstance(item, dict) and "message" in item:
                    return item["message"].get("content", "")
            return json.dumps(data, indent=2)
        else:
            return None
    except Exception:
        return None


def call_search_fallback(prompt_text, session, role, lang):
    search_results = session.sql(
        """SELECT DRUG_A_NAME, DRUG_B_NAME, SEVERITY, MECHANISM,
                  CLINICAL_EFFECT, MANAGEMENT, PATIENT_SUMMARY,
                  ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
           FROM TABLE(
               HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_SEARCH!SEARCH(
                   QUERY => ?, LIMIT => 5))""",
        params=[prompt_text]
    ).to_pandas()

    if not search_results.empty:
        context_parts = []
        for _, r in search_results.iterrows():
            context_parts.append(
                f"- {r['DRUG_A_NAME']} + {r['DRUG_B_NAME']} ({r['SEVERITY']}): "
                f"{r['CLINICAL_EFFECT']}. Management: {r['MANAGEMENT']}. "
                f"Alt for {r['DRUG_A_NAME']}: {r['ALTERNATIVE_FOR_A']}. "
                f"Alt for {r['DRUG_B_NAME']}: {r['ALTERNATIVE_FOR_B']}."
            )
        context = "\n".join(context_parts)
    else:
        context = "No specific drug interaction data found for this query."

    persona = "You are speaking to a patient. Use plain language." if role == "patient" else "You are speaking to a healthcare provider. Use clinical terminology."
    lang_instruction = f" Respond entirely in {LANG_NAMES.get(lang, lang)}." if lang != "en" else ""

    safe_prompt = prompt_text.replace("$$", "$ $")
    safe_context = context.replace("$$", "$ $")

    result = session.sql(
        f"""SELECT AI_COMPLETE(
            'claude-sonnet-4-6',
            CONCAT(
                'You are a clinical pharmacist AI assistant. ', $${persona}$$, ' ',
                'Answer based on the drug interaction data below. ',
                'Always cite severity levels. All data is AI-generated and not clinically validated. ',
                'If the data does not cover the question, say so clearly.',
                $${lang_instruction}$$,
                CHR(10), CHR(10), 'DRUG INTERACTION DATA:', CHR(10),
                $${safe_context}$$,
                CHR(10), CHR(10), 'QUESTION: ', $${safe_prompt}$$
            ),
            OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 800)
        ) AS RESPONSE"""
    ).collect()

    return result[0]["RESPONSE"] if result else "No response received."


# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input(translate("Ask about medications, interactions, or patients...", lang, session)):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(translate("Thinking...", lang, session)):
            try:
                # Try the agent REST API first
                answer = call_agent_rest(prompt, session)

                if not answer:
                    # Fall back to search + AI_COMPLETE
                    answer = call_search_fallback(prompt, session, role, lang)

                # Translate if needed and answer came from agent (already English)
                if lang != "en" and answer:
                    answer = translate(answer, lang, session)

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
