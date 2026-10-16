"""
Utility: Cortex Agent client wrapper for the chat interface.
"""
from snowflake.snowpark.context import get_active_session


def query_agent(question: str, session=None):
    """Send a question to the Drug Interaction Cortex Agent."""
    if session is None:
        session = get_active_session()

    result = session.sql(f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'claude-3-5-sonnet',
            ARRAY_CONSTRUCT(
                OBJECT_CONSTRUCT('role', 'system', 'content',
                    'You are a clinical pharmacist AI. Answer drug interaction and medication questions.
                     Be specific about severity levels and always recommend provider consultation.'),
                OBJECT_CONSTRUCT('role', 'user', 'content', $${question}$$)
            ),
            OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 1024)
        ) AS RESPONSE
    """).collect()

    return result[0]["RESPONSE"] if result else "No response received."


def search_interactions(query: str, session=None, limit: int = 5):
    """Search the drug interaction Cortex Search service."""
    if session is None:
        session = get_active_session()

    # Using Cortex Search service
    result = session.sql(f"""
        SELECT
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
            HEALTHCARE_DW.PHARMACY.DRUG_INTERACTION_SEARCH!SEARCH(
                QUERY => $${query}$$,
                LIMIT => {limit}
            )
        )
    """).to_pandas()

    return result
