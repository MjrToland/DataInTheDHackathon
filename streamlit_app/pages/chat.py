"""
Chat Interface — Conversational Q&A backed by the Cortex Agent.
Patients and providers can ask natural-language questions about medications,
interactions, and alternatives.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session
import json

st.set_page_config(page_title="Medication Chat", page_icon="💬", layout="wide")
session = get_active_session()

st.title("Medication Chat")
st.markdown("Ask questions about drug interactions, medications, and patient safety.")

# Language selection for responses
LANG_NAMES = {
    "en": "English", "es": "Spanish", "ar": "Arabic", "zh": "Chinese",
    "fr": "French", "pt": "Portuguese", "de": "German", "ko": "Korean",
    "vi": "Vietnamese", "ja": "Japanese"
}

response_lang = st.sidebar.selectbox(
    "Response Language",
    list(LANG_NAMES.keys()),
    format_func=lambda x: LANG_NAMES[x],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
**Example questions:**
- What are the interactions for patient 53115?
- Is it safe to take Sertraline with Ibuprofen?
- What alternatives exist for Metformin?
- How many patients have critical interactions?
- Show me all patients on both SSRIs and NSAIDs
""")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask about medications, interactions, or patients..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Call the Cortex Agent
                agent_response = session.sql(f"""
                    SELECT SNOWFLAKE.CORTEX.COMPLETE(
                        'claude-3-5-sonnet',
                        ARRAY_CONSTRUCT(
                            OBJECT_CONSTRUCT('role', 'system', 'content',
                                'You are a clinical pharmacist AI assistant. You have access to a healthcare database
                                 with patient prescriptions, drug interactions, and clinical encounters.
                                 Answer questions about drug interactions, patient medications, and treatment alternatives.
                                 Be specific, cite severity levels, and always recommend consulting a provider for changes.
                                 If you reference specific data, mention the source tables.'),
                            OBJECT_CONSTRUCT('role', 'user', 'content', '{prompt.replace("'", "''")}')
                        ),
                        OBJECT_CONSTRUCT(
                            'temperature', 0.3,
                            'max_tokens', 1024
                        )
                    ) AS RESPONSE
                """).collect()

                answer = agent_response[0]["RESPONSE"]

                # Try to parse if it's JSON
                try:
                    parsed = json.loads(answer)
                    if isinstance(parsed, dict) and "choices" in parsed:
                        answer = parsed["choices"][0]["messages"]
                    elif isinstance(parsed, dict) and "messages" in parsed:
                        answer = parsed["messages"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

                # Translate if needed
                if response_lang != "en":
                    translated = session.sql(f"""
                        SELECT SNOWFLAKE.CORTEX.TRANSLATE(
                            $${answer}$$, 'en', '{response_lang}'
                        ) AS TRANSLATED
                    """).collect()
                    answer = translated[0]["TRANSLATED"]

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
