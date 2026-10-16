"""
Utility: Cortex Agent client wrapper for the chat interface.
"""
from snowflake.snowpark.context import get_active_session


def query_agent(question: str, session=None):
    """Send a question to the Drug Interaction Cortex Agent.
    
    Falls back to Cortex Search + AI_COMPLETE if the agent is unavailable.
    """
    if session is None:
        session = get_active_session()

    # Try the agent first
    try:
        result = session.sql(
            """SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
                'HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_AGENT',
                ?,
                TRUE
            ) AS RESPONSE""",
            params=['{"messages": [{"role": "user", "content": [{"type": "text", "text": "' + question.replace('"', '\\"') + '"}]}]}']
        ).collect()
        return result[0]["RESPONSE"] if result else "No response received."
    except Exception:
        # Fallback: search + AI_COMPLETE
        return _search_and_complete(question, session)


def _search_and_complete(question: str, session):
    """Fallback: use Cortex Search for context, then AI_COMPLETE for answer."""
    search_results = search_interactions(question, session, limit=5)
    
    if not search_results.empty:
        context_parts = []
        for _, r in search_results.iterrows():
            context_parts.append(
                f"- {r['DRUG_A_NAME']} + {r['DRUG_B_NAME']} ({r['SEVERITY']}): "
                f"{r['CLINICAL_EFFECT']}. Management: {r['MANAGEMENT']}"
            )
        context = "\n".join(context_parts)
    else:
        context = "No specific interaction data found."

    safe_q = question.replace("$$", "$ $")
    safe_ctx = context.replace("$$", "$ $")

    result = session.sql(
        f"""SELECT AI_COMPLETE(
            'claude-sonnet-4-6',
            CONCAT(
                'You are a clinical pharmacist AI. Answer based on this data (AI-generated, not clinically validated):',
                CHR(10), $${safe_ctx}$$, CHR(10), CHR(10), 'Question: ', $${safe_q}$$
            ),
            OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 800)
        ) AS RESPONSE"""
    ).collect()

    return result[0]["RESPONSE"] if result else "No response received."


def search_interactions(query: str, session=None, limit: int = 5):
    """Search the drug interaction Cortex Search service."""
    if session is None:
        session = get_active_session()

    result = session.sql(
        """SELECT
            DRUG_A_NAME,
            DRUG_B_NAME,
            SEVERITY,
            MECHANISM,
            CLINICAL_EFFECT,
            MANAGEMENT,
            PATIENT_SUMMARY,
            ALTERNATIVE_FOR_A,
            ALTERNATIVE_FOR_B
        FROM TABLE(
            HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_SEARCH!SEARCH(
                QUERY => ?,
                LIMIT => ?
            )
        )""",
        params=[query, limit]
    ).to_pandas()

    return result
