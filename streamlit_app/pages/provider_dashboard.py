"""
Provider Dashboard — Shows a provider's patient panel with flagged drug interactions,
sorted by severity. Providers can review alerts and trigger email notifications.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Provider Dashboard", page_icon="🩺", layout="wide")
session = get_active_session()

st.title("Provider Dashboard")
st.markdown("View your patient panel and flagged drug interactions.")

# Provider selector
providers = session.sql("""
    SELECT PROVIDER_ID, FIRST_NAME || ' ' || LAST_NAME || ' (' || SPECIALTY || ')' AS DISPLAY
    FROM HEALTHCARE_DW.CORE.PROVIDERS
    WHERE STATUS = 'ACTIVE'
    ORDER BY LAST_NAME
    LIMIT 50
""").to_pandas()

selected = st.selectbox("Select Provider", providers["DISPLAY"].tolist())
if selected:
    provider_id = int(providers[providers["DISPLAY"] == selected]["PROVIDER_ID"].iloc[0])

    # Summary metrics for this provider
    metrics = session.sql(f"""
        SELECT
            COUNT(DISTINCT PATIENT_ID) AS TOTAL_PATIENTS,
            COUNT(DISTINCT CASE WHEN SEVERITY = 'CRITICAL' THEN PATIENT_ID END) AS CRITICAL,
            COUNT(DISTINCT CASE WHEN SEVERITY = 'HIGH' THEN PATIENT_ID END) AS HIGH_SEV,
            COUNT(DISTINCT CASE WHEN SEVERITY = 'MODERATE' THEN PATIENT_ID END) AS MODERATE
        FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
        WHERE PRESCRIBER_A_ID = {provider_id} OR PRESCRIBER_B_ID = {provider_id}
    """).to_pandas()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", int(metrics["TOTAL_PATIENTS"].iloc[0]))
    c2.metric("Critical", int(metrics["CRITICAL"].iloc[0]))
    c3.metric("High", int(metrics["HIGH_SEV"].iloc[0]))
    c4.metric("Moderate", int(metrics["MODERATE"].iloc[0]))

    st.markdown("---")

    # Severity filter
    severity_filter = st.multiselect(
        "Filter by Severity",
        ["CRITICAL", "HIGH", "MODERATE", "LOW"],
        default=["CRITICAL", "HIGH"]
    )

    if severity_filter:
        sev_list = ", ".join(f"'{s}'" for s in severity_filter)
        panel = session.sql(f"""
            SELECT
                PATIENT_ID,
                FIRST_NAME || ' ' || LAST_NAME AS PATIENT_NAME,
                SEVERITY,
                DRUG_A_NAME,
                DRUG_B_NAME,
                CLINICAL_EFFECT,
                MANAGEMENT,
                ALTERNATIVE_FOR_A,
                ALTERNATIVE_FOR_B,
                PRESCRIBER_A_NAME,
                PRESCRIBER_B_NAME,
                PREFERRED_LANGUAGE
            FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
            WHERE (PRESCRIBER_A_ID = {provider_id} OR PRESCRIBER_B_ID = {provider_id})
              AND SEVERITY IN ({sev_list})
            ORDER BY
                CASE SEVERITY
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MODERATE' THEN 3 ELSE 4
                END,
                LAST_NAME, FIRST_NAME
            LIMIT 100
        """).to_pandas()

        st.subheader(f"Flagged Interactions ({len(panel)} alerts)")

        for _, row in panel.iterrows():
            sev = row["SEVERITY"]
            color = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            with st.expander(f"{color} {sev} — {row['PATIENT_NAME']}: {row['DRUG_A_NAME']} + {row['DRUG_B_NAME']}"):
                st.markdown(f"**Clinical Effect:** {row['CLINICAL_EFFECT']}")
                st.markdown(f"**Management:** {row['MANAGEMENT']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Alternative for {row['DRUG_A_NAME']}:** {row['ALTERNATIVE_FOR_A']}")
                    st.markdown(f"**Prescribed by:** {row['PRESCRIBER_A_NAME']}")
                with col_b:
                    st.markdown(f"**Alternative for {row['DRUG_B_NAME']}:** {row['ALTERNATIVE_FOR_B']}")
                    st.markdown(f"**Prescribed by:** {row['PRESCRIBER_B_NAME']}")

                st.markdown(f"**Patient Language:** {row['PREFERRED_LANGUAGE']}")

                # Email alert button
                if st.button(f"Send Alert Email", key=f"email_{row['PATIENT_ID']}_{row['DRUG_A_NAME']}_{row['DRUG_B_NAME']}"):
                    session.sql(f"""
                        INSERT INTO HEALTHCARE_DW.PHARMACY.ALERT_EMAIL_LOG
                            (PATIENT_ID, INTERACTION_ID, PROVIDER_ID, PROVIDER_NAME, SEVERITY, EMAIL_SUBJECT, EMAIL_BODY)
                        SELECT
                            {row['PATIENT_ID']},
                            INTERACTION_ID,
                            {provider_id},
                            '{selected.replace("'", "''")}',
                            '{sev}',
                            '[{sev} ALERT] {row["DRUG_A_NAME"]} + {row["DRUG_B_NAME"]} — {row["PATIENT_NAME"]}',
                            SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet',
                                'Write a 3-paragraph medical alert email about a ' || SEVERITY ||
                                ' drug interaction between ' || DRUG_A_NAME || ' and ' || DRUG_B_NAME ||
                                '. Clinical effect: ' || CLINICAL_EFFECT || '. Management: ' || MANAGEMENT)
                        FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
                        WHERE PATIENT_ID = {row['PATIENT_ID']}
                          AND DRUG_A_NAME = '{row["DRUG_A_NAME"]}'
                          AND DRUG_B_NAME = '{row["DRUG_B_NAME"]}'
                        LIMIT 1
                    """).collect()
                    st.success("Alert email generated and logged.")
