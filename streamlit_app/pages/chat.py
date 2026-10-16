"""
Chat Interface — Conversational Q&A using Cortex Search + AI_COMPLETE.
Personalizes context based on whether the user is a provider or patient.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Medication Chat", page_icon="💬", layout="wide")
session = get_active_session()

role = st.session_state.get("role")
if not role:
    st.warning("Please sign in from the home page.")
    st.stop()

st.title("Medication Chat")
st.markdown("Ask questions about drug interactions, medications, and patient safety.")
st.caption("All answers are AI-generated and not clinically validated. Always consult a provider.")

LANG_NAMES = {
    "en": "English", "es": "Spanish", "ar": "Arabic", "zh": "Chinese",
    "fr": "French", "pt": "Portuguese", "de": "German", "ko": "Korean",
    "vi": "Vietnamese", "ja": "Japanese"
}

response_lang = st.sidebar.selectbox(
    "Response Language", list(LANG_NAMES.keys()),
    format_func=lambda x: LANG_NAMES[x], index=0
)

# Contextual hints based on role
if role == "provider":
    st.sidebar.markdown(f"**Provider:** {st.session_state.get('provider_name', '')}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Example questions:**
    - What are the critical interactions in my patient panel?
    - Is it safe to prescribe an SSRI with an NSAID?
    - What alternatives exist for Metformin?
    """)
elif role == "patient":
    st.sidebar.markdown(f"**Patient:** {st.session_state.get('patient_name', '')}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Example questions:**
    - Do any of my medications interact?
    - What does my pharmacist note say about Sertraline?
    - What are safer alternatives for my pain medication?
    """)
else:
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Example questions:**
    - What are the interactions for Sertraline?
    - Tell me about Trazodone + Azithromycin
    - How many patients have critical interactions?
    """)

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about medications, interactions, or patients..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching drug interaction knowledge base..."):
            try:
                # Search drug interaction corpus
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

                # Build persona based on role
                if role == "patient":
                    persona = "You are speaking to a patient. Use plain language. Be reassuring but accurate."
                else:
                    persona = "You are speaking to a healthcare provider. Use clinical terminology."

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
                            CHR(10), CHR(10), 'DRUG INTERACTION DATA:', CHR(10),
                            $${safe_context}$$,
                            CHR(10), CHR(10), 'QUESTION: ', $${safe_prompt}$$
                        ),
                        OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 800)
                    ) AS RESPONSE"""
                ).collect()

                answer = answer_result[0]["RESPONSE"]

                if response_lang != "en" and answer:
                    translated = session.sql(
                        "SELECT AI_TRANSLATE(?, 'en', ?) AS TRANSLATED",
                        params=[answer, response_lang]
                    ).collect()
                    answer = translated[0]["TRANSLATED"]

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
