"""
Provider Dashboard — Shows a provider's patient panel with flagged drug interactions,
sorted by severity. Includes email alert sign-up.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Provider Dashboard", page_icon="🩺", layout="wide")
session = get_active_session()
render_sidebar(session)

role = st.session_state.get("role")
provider_id = st.session_state.get("provider_id")

# --- Provider resolution ---
if role == "provider" and provider_id:
    provider_name = st.session_state.get("provider_name", "")
    st.title("Provider Dashboard")
    st.markdown(f"**{provider_name}**")
elif role == "admin":
    st.title("Provider Dashboard (Admin)")
    providers = session.sql("""
        SELECT PROVIDER_ID, FIRST_NAME || ' ' || LAST_NAME || ' (' || SPECIALTY || ')' AS DISPLAY
        FROM HEALTHCARE_DW.CORE.PROVIDERS WHERE STATUS = 'ACTIVE'
        ORDER BY LAST_NAME LIMIT 50
    """).to_pandas()
    selected = st.selectbox("Select Provider", providers["DISPLAY"].tolist())
    if selected:
        provider_id = int(providers[providers["DISPLAY"] == selected]["PROVIDER_ID"].iloc[0])
else:
    if role == "patient":
        st.error("This page is for providers. Please use the Patient Portal or Interaction Checker.")
    else:
        st.warning("Please sign in as a provider or admin from the home page.")
    st.stop()

st.caption("Drug interaction data is AI-generated and not clinically validated.")

# --- Email sign-up banner ---
st.markdown("---")
sub = session.sql(
    "SELECT EMAIL, SUBSCRIBED FROM HEALTHCARE_DW.DDI_APP.PROVIDER_EMAIL_SUBSCRIPTIONS WHERE PROVIDER_ID = ?",
    params=[provider_id]
).to_pandas()

if sub.empty:
    with st.container():
        st.info("You're not signed up for email alerts. Get notified when critical drug interactions are found in your patient panel.")
        email_col, btn_col = st.columns([3, 1])
        with email_col:
            email_input = st.text_input("Your email address", placeholder="you@hospital.org", key="email_signup")
        with btn_col:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Subscribe", type="primary", key="btn_subscribe"):
                if email_input and "@" in email_input:
                    session.sql(
                        """INSERT INTO HEALTHCARE_DW.DDI_APP.PROVIDER_EMAIL_SUBSCRIPTIONS
                           (PROVIDER_ID, EMAIL) VALUES (?, ?)""",
                        params=[provider_id, email_input]
                    ).collect()
                    st.success(f"Subscribed! Alerts will be sent to {email_input}")
                    st.experimental_rerun()
                else:
                    st.error("Enter a valid email address.")
elif sub.iloc[0]["SUBSCRIBED"]:
    col_info, col_unsub = st.columns([4, 1])
    with col_info:
        st.success(f"Email alerts active: **{sub.iloc[0]['EMAIL']}**")
    with col_unsub:
        if st.button("Unsubscribe", key="btn_unsub"):
            session.sql(
                "UPDATE HEALTHCARE_DW.DDI_APP.PROVIDER_EMAIL_SUBSCRIPTIONS SET SUBSCRIBED = FALSE WHERE PROVIDER_ID = ?",
                params=[provider_id]
            ).collect()
            st.experimental_rerun()
else:
    col_info, col_resub = st.columns([4, 1])
    with col_info:
        st.warning("Email alerts paused.")
    with col_resub:
        if st.button("Re-subscribe", key="btn_resub"):
            session.sql(
                "UPDATE HEALTHCARE_DW.DDI_APP.PROVIDER_EMAIL_SUBSCRIPTIONS SET SUBSCRIBED = TRUE WHERE PROVIDER_ID = ?",
                params=[provider_id]
            ).collect()
            st.experimental_rerun()

st.markdown("---")

# --- Summary metrics ---
metrics = session.sql(
    """SELECT
        COUNT(DISTINCT PATIENT_ID) AS TOTAL_PATIENTS,
        COUNT(DISTINCT CASE WHEN SEVERITY = 'CRITICAL' THEN PATIENT_ID END) AS CRITICAL,
        COUNT(DISTINCT CASE WHEN SEVERITY = 'HIGH' THEN PATIENT_ID END) AS HIGH_SEV,
        COUNT(DISTINCT CASE WHEN SEVERITY = 'MODERATE' THEN PATIENT_ID END) AS MODERATE
    FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
    WHERE PRESCRIBER_A_ID = ? OR PRESCRIBER_B_ID = ?""",
    params=[provider_id, provider_id]
).to_pandas()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Patients", int(metrics["TOTAL_PATIENTS"].iloc[0]))
c2.metric("Critical", int(metrics["CRITICAL"].iloc[0]))
c3.metric("High", int(metrics["HIGH_SEV"].iloc[0]))
c4.metric("Moderate", int(metrics["MODERATE"].iloc[0]))

st.markdown("---")

# --- Severity filter + alert list ---
severity_filter = st.multiselect(
    "Filter by Severity",
    ["CRITICAL", "HIGH", "MODERATE", "LOW"],
    default=["CRITICAL", "HIGH"]
)

if severity_filter:
    params = [provider_id, provider_id] + severity_filter

    panel = session.sql(
        f"""SELECT
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
            PREFERRED_LANGUAGE,
            INTERACTION_ID
        FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
        WHERE (PRESCRIBER_A_ID = ? OR PRESCRIBER_B_ID = ?)
          AND SEVERITY IN ({", ".join(["?"] * len(severity_filter))})
        ORDER BY
            CASE SEVERITY
                WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'MODERATE' THEN 3 ELSE 4
            END,
            LAST_NAME, FIRST_NAME
        LIMIT 100""",
        params=params
    ).to_pandas()

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
            st.caption("Drug interaction data is AI-generated and not clinically validated.")
