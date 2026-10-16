"""
Chat Interface — Conversational Q&A using Cortex Search + AI_COMPLETE.
Personalizes context based on whether the user is a provider or patient.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session
from utils.sidebar import render_sidebar, translate

st.set_page_config(page_title="Medication Chat", page_icon="💬", layout="wide")
session = get_active_session()
lang = render_sidebar(session, show_language=True)

role = st.session_state.get("role")
if not role:
    st.warning("Please sign in from the home page.")
    st.stop()

st.title(translate("Medication Chat", lang, session))
st.markdown(translate("Ask questions about drug interactions, medications, and patient safety.", lang, session))
st.caption(translate("All answers are AI-generated and not clinically validated. Always consult a provider.", lang, session))

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
        with st.spinner(translate("Searching drug interaction knowledge base...", lang, session)):
            try:
                search_results = session.sql(
                    """SELECT DRUG_A_NAME, DRUG_B_NAME, SEVERITY, MECHANISM,
                              CLINICAL_EFFECT, MANAGEMENT, PATIENT_SUMMARY,
                              ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
                       FROM TABLE(
                           HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_SEARCH!SEARCH(
                               QUERY => ?, LIMIT => 5))""",
                    params=[prompt]
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

                if role == "patient":
                    persona = "You are speaking to a patient. Use plain language. Be reassuring but accurate."
                else:
                    persona = "You are speaking to a healthcare provider. Use clinical terminology."

                # Ask for response in the selected language
                lang_instruction = ""
                if lang != "en":
                    from utils.sidebar import LANG_NAMES
                    lang_instruction = f" Respond entirely in {LANG_NAMES.get(lang, lang)}."

                safe_prompt = prompt.replace("$$", "$ $")
                safe_context = context.replace("$$", "$ $")

                answer_result = session.sql(
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

                answer = answer_result[0]["RESPONSE"]

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
