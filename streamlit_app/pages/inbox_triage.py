"""
Inbox Triage — Self-service tool that auto-classifies drug interaction alerts
by severity and urgency. Removes manual review from provider inboxes by
auto-generating email drafts for critical alerts.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Inbox Triage", page_icon="📋", layout="wide")
session = get_active_session()

role = st.session_state.get("role")
if role not in ("provider", "admin"):
    st.warning("Please sign in as a provider or admin from the home page.")
    st.stop()

st.title("Inbox Triage")
st.markdown("Auto-classified drug interaction alerts. Critical alerts generate email drafts automatically.")
st.caption("Drug interaction data is AI-generated and not clinically validated.")

tab_pending, tab_sent, tab_stats = st.tabs(["Pending Alerts", "Sent Alerts", "Statistics"])

with tab_pending:
    st.subheader("Unresolved Alerts")
    st.markdown("Alerts not yet emailed to providers, sorted by severity.")

    col1, col2 = st.columns(2)
    with col1:
        sev_filter = st.multiselect(
            "Severity", ["CRITICAL", "HIGH", "MODERATE", "LOW"],
            default=["CRITICAL", "HIGH"]
        )
    with col2:
        limit = st.slider("Max alerts to show", 10, 200, 50)

    if sev_filter:
        placeholders = ", ".join(["?"] * len(sev_filter))
        params = sev_filter + [limit]

        pending = session.sql(
            f"""SELECT
                a.PATIENT_ID,
                a.FIRST_NAME || ' ' || a.LAST_NAME AS PATIENT,
                a.SEVERITY,
                a.DRUG_A_NAME,
                a.DRUG_B_NAME,
                a.CLINICAL_EFFECT,
                a.MANAGEMENT,
                a.PRESCRIBER_A_NAME AS PROVIDER_A,
                a.PRESCRIBER_B_NAME AS PROVIDER_B,
                a.INTERACTION_ID
            FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS a
            WHERE a.SEVERITY IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1 FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG l
                  WHERE l.PATIENT_ID = a.PATIENT_ID
                    AND l.INTERACTION_ID = a.INTERACTION_ID
              )
            ORDER BY
                CASE a.SEVERITY
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MODERATE' THEN 3 ELSE 4
                END,
                a.LAST_NAME
            LIMIT ?""",
            params=params
        ).to_pandas()

        if pending.empty:
            st.success("No pending alerts matching your filters.")
        else:
            st.markdown(f"**{len(pending)} pending alerts**")

            if st.button("Generate Email Drafts for All Shown Alerts", type="primary"):
                with st.spinner("Generating email drafts..."):
                    session.sql(
                        "CALL HEALTHCARE_DW.DDI_APP.GENERATE_INTERACTION_ALERTS()"
                    ).collect()
                    st.success("Email drafts generated. Check the Sent Alerts tab.")
                    st.rerun()

            for _, row in pending.iterrows():
                sev = row["SEVERITY"]
                icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")

                with st.expander(f"{icon} {sev} — {row['PATIENT']}: {row['DRUG_A_NAME']} + {row['DRUG_B_NAME']}"):
                    st.markdown(f"**Effect:** {row['CLINICAL_EFFECT']}")
                    st.markdown(f"**Management:** {row['MANAGEMENT']}")
                    st.markdown(f"**Providers:** {row['PROVIDER_A']} / {row['PROVIDER_B']}")

with tab_sent:
    st.subheader("Sent Alert Log")
    sent = session.sql("""
        SELECT
            SENT_AT,
            SEVERITY,
            PROVIDER_NAME,
            EMAIL_SUBJECT,
            STATUS
        FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG
        ORDER BY SENT_AT DESC
        LIMIT 100
    """).to_pandas()

    if sent.empty:
        st.info("No alerts have been drafted yet.")
    else:
        st.dataframe(sent, use_container_width=True, hide_index=True)

with tab_stats:
    st.subheader("Alert Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Alerts by Severity**")
        by_sev = session.sql("""
            SELECT SEVERITY, COUNT(DISTINCT PATIENT_ID) AS PATIENTS,
                   COUNT(*) AS TOTAL_ALERTS
            FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
            GROUP BY SEVERITY
            ORDER BY CASE SEVERITY
                WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'MODERATE' THEN 3 ELSE 4 END
        """).to_pandas()
        if not by_sev.empty:
            st.dataframe(by_sev, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**Top Drug Pairs by Alert Count**")
        top_pairs = session.sql("""
            SELECT
                DRUG_A_NAME || ' + ' || DRUG_B_NAME AS PAIR,
                SEVERITY,
                COUNT(DISTINCT PATIENT_ID) AS PATIENTS
            FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
            GROUP BY DRUG_A_NAME, DRUG_B_NAME, SEVERITY
            ORDER BY PATIENTS DESC
            LIMIT 10
        """).to_pandas()
        if not top_pairs.empty:
            st.dataframe(top_pairs, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Email subscription stats
    st.markdown("**Provider Email Subscriptions**")
    sub_stats = session.sql("""
        SELECT
            COUNT(*) AS TOTAL_SUBSCRIBED,
            COUNT_IF(SUBSCRIBED = TRUE) AS ACTIVE,
            COUNT_IF(SUBSCRIBED = FALSE) AS PAUSED
        FROM HEALTHCARE_DW.DDI_APP.PROVIDER_EMAIL_SUBSCRIPTIONS
    """).to_pandas()
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Total Signed Up", int(sub_stats["TOTAL_SUBSCRIBED"].iloc[0]))
    sc2.metric("Active", int(sub_stats["ACTIVE"].iloc[0]))
    sc3.metric("Paused", int(sub_stats["PAUSED"].iloc[0]))

    st.markdown("---")
    st.markdown("**Polypharmacy Distribution**")
    poly = session.sql("""
        WITH rx_counts AS (
            SELECT PATIENT_ID, COUNT(DISTINCT MEDICATION_ID) AS NUM_MEDS
            FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS
            WHERE STATUS = 'FILLED'
            GROUP BY PATIENT_ID
        )
        SELECT NUM_MEDS AS MEDICATIONS, COUNT(*) AS PATIENTS
        FROM rx_counts
        WHERE NUM_MEDS >= 2
        GROUP BY NUM_MEDS
        ORDER BY NUM_MEDS
    """).to_pandas()
    if not poly.empty:
        st.bar_chart(poly.set_index("MEDICATIONS"))
