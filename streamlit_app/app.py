"""
Drug Interaction Intelligence Platform
Main Streamlit application entry point.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(
    page_title="Drug Interaction Intelligence",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

session = get_active_session()

# Sidebar navigation
st.sidebar.title("Drug Interaction Intelligence")
st.sidebar.markdown("---")
st.sidebar.markdown("**DataInTheD Hackathon 2026**")
st.sidebar.markdown("""
**Snowflake Features:**
- Cortex Agents
- Semantic Views
- Cortex Search
- AI_TRANSLATE
- Restricted Caller's Rights
""")

# Main landing page
st.title("Drug Interaction Intelligence Platform")
st.markdown("""
AI-powered drug interaction detection and alerting for healthcare providers and patients.

### How it works

1. **Detect** — Cross-references patient prescriptions against known drug interactions
   sourced from DrugBank and FDA FAERS adverse event data
2. **Alert** — Automatically emails providers when CRITICAL or HIGH severity
   interactions are detected in their patient panel
3. **Empower** — Multilingual AI chat interface for providers and patients to ask
   questions about their medications
4. **Triage** — Self-service inbox that auto-classifies alerts by severity,
   removing manual review from provider workflows

---
""")

# Quick stats
col1, col2, col3, col4 = st.columns(4)

with col1:
    result = session.sql("""
        SELECT COUNT(DISTINCT PATIENT_ID)
        FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS
        WHERE STATUS IN ('ACTIVE', 'FILLED')
    """).collect()
    st.metric("Active Patients", f"{result[0][0]:,}")

with col2:
    result = session.sql("""
        SELECT COUNT(*) FROM HEALTHCARE_DW.PHARMACY.DRUG_INTERACTIONS
        WHERE SEVERITY IN ('CRITICAL', 'HIGH')
    """).collect()
    st.metric("High-Risk Interactions", f"{result[0][0]:,}")

with col3:
    result = session.sql("""
        SELECT COUNT(DISTINCT PATIENT_ID)
        FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
        WHERE SEVERITY IN ('CRITICAL', 'HIGH')
    """).collect()
    st.metric("Patients at Risk", f"{result[0][0]:,}")

with col4:
    result = session.sql("""
        SELECT COUNT(*) FROM HEALTHCARE_DW.PHARMACY.ALERT_EMAIL_LOG
    """).collect()
    st.metric("Alerts Sent", f"{result[0][0]:,}")

st.markdown("---")

# Severity distribution chart
st.subheader("Interaction Severity Distribution")
severity_df = session.sql("""
    SELECT SEVERITY, COUNT(*) AS COUNT
    FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
    GROUP BY SEVERITY
    ORDER BY
        CASE SEVERITY
            WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
            WHEN 'MODERATE' THEN 3 ELSE 4
        END
""").to_pandas()

if not severity_df.empty:
    st.bar_chart(severity_df.set_index("SEVERITY"))

# Top interaction pairs
st.subheader("Most Common Dangerous Drug Pairs")
top_pairs = session.sql("""
    SELECT
        DRUG_A_NAME || ' + ' || DRUG_B_NAME AS DRUG_PAIR,
        SEVERITY,
        COUNT(DISTINCT PATIENT_ID) AS AFFECTED_PATIENTS,
        CLINICAL_EFFECT
    FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
    WHERE SEVERITY IN ('CRITICAL', 'HIGH')
    GROUP BY DRUG_A_NAME, DRUG_B_NAME, SEVERITY, CLINICAL_EFFECT
    ORDER BY AFFECTED_PATIENTS DESC
    LIMIT 10
""").to_pandas()

if not top_pairs.empty:
    st.dataframe(top_pairs, use_container_width=True, hide_index=True)
