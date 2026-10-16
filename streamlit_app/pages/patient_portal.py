"""
Patient Portal — Personalized view showing current medications,
flagged interactions, and translated summaries in the patient's language.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Patient Portal", page_icon="👤", layout="wide")
session = get_active_session()

role = st.session_state.get("role")
pid = st.session_state.get("patient_id")
patient_name = st.session_state.get("patient_name", "")
lang = st.session_state.get("patient_lang", "en")

LANG_NAMES = {
    "en": "English", "es": "Spanish", "ar": "Arabic", "zh": "Chinese",
    "fr": "French", "pt": "Portuguese", "de": "German", "ko": "Korean",
    "vi": "Vietnamese", "ja": "Japanese"
}

# --- Patient resolution ---
if role == "patient" and pid:
    st.title("Patient Portal")
    st.markdown(f"### Welcome, {patient_name}")
    st.markdown(f"**Language preference:** {LANG_NAMES.get(lang, lang)}")
elif role == "admin":
    st.title("Patient Portal (Admin)")
    st.markdown("Look up any patient by last name and date of birth.")
    search_col1, search_col2 = st.columns(2)
    with search_col1:
        last_name = st.text_input("Last Name")
    with search_col2:
        dob = st.date_input("Date of Birth", value=None)

    if last_name and dob:
        patients = session.sql(
            """SELECT p.PATIENT_ID, p.FIRST_NAME, p.LAST_NAME,
                      COALESCE(pp.PREFERRED_LANGUAGE, 'en') AS PREFERRED_LANGUAGE
               FROM HEALTHCARE_DW.CORE.PATIENTS p
               LEFT JOIN HEALTHCARE_DW.DDI_APP.PATIENT_PREFERENCES pp ON p.PATIENT_ID = pp.PATIENT_ID
               WHERE UPPER(p.LAST_NAME) = UPPER(?) AND p.DATE_OF_BIRTH = ?""",
            params=[last_name, str(dob)]
        ).to_pandas()
        if patients.empty:
            st.warning("No patient found.")
            st.stop()
        row = patients.iloc[0]
        pid = int(row["PATIENT_ID"])
        patient_name = f"{row['FIRST_NAME']} {row['LAST_NAME']}"
        lang = row["PREFERRED_LANGUAGE"]
        st.markdown(f"### {patient_name}")
    else:
        st.stop()
else:
    st.warning("Please sign in as a patient or admin from the home page.")
    st.stop()

st.caption("Drug interaction data is AI-generated and not clinically validated.")

lang_override = st.selectbox(
    "Display language",
    list(LANG_NAMES.keys()),
    format_func=lambda x: LANG_NAMES[x],
    index=list(LANG_NAMES.keys()).index(lang) if lang in LANG_NAMES else 0
)

st.markdown("---")

# --- Current medications ---
st.subheader("Your Current Medications")
meds = session.sql(
    """SELECT
        rx.MEDICATION_NAME, m.DRUG_CLASS, rx.DOSAGE, rx.FREQUENCY,
        rx.PRESCRIBED_DATE, rx.REFILLS_REMAINING,
        prov.FIRST_NAME || ' ' || prov.LAST_NAME AS PRESCRIBER
    FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx
    JOIN HEALTHCARE_DW.PHARMACY.MEDICATIONS m ON rx.MEDICATION_ID = m.MEDICATION_ID
    LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov ON rx.PROVIDER_ID = prov.PROVIDER_ID
    WHERE rx.PATIENT_ID = ? AND rx.STATUS = 'FILLED'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rx.MEDICATION_ID ORDER BY rx.PRESCRIBED_DATE DESC) = 1
    ORDER BY rx.MEDICATION_NAME""",
    params=[pid]
).to_pandas()

if not meds.empty:
    st.dataframe(meds, use_container_width=True, hide_index=True)
else:
    st.info("No active medications found.")

st.markdown("---")

# --- Drug interaction alerts ---
st.subheader("Safety Alerts")
alerts = session.sql(
    """SELECT INTERACTION_ID, DRUG_A_NAME, DRUG_B_NAME, SEVERITY,
              PATIENT_SUMMARY, MANAGEMENT, ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
    FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
    WHERE PATIENT_ID = ?
    ORDER BY CASE SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MODERATE' THEN 3 ELSE 4 END""",
    params=[pid]
).to_pandas()

if alerts.empty:
    st.success("No drug interaction alerts for your current medications.")
else:
    st.warning(f"**{len(alerts)} interaction(s) detected** in your current medications.")

    for _, alert in alerts.iterrows():
        sev = alert["SEVERITY"]
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")

        with st.expander(f"{icon} {sev}: {alert['DRUG_A_NAME']} + {alert['DRUG_B_NAME']}"):
            summary = alert["PATIENT_SUMMARY"] or ""
            mgmt = alert["MANAGEMENT"] or ""

            if lang_override != "en" and summary:
                translated = session.sql(
                    "SELECT AI_TRANSLATE(?, 'en', ?) AS T_SUMMARY, AI_TRANSLATE(?, 'en', ?) AS T_MGMT",
                    params=[summary, lang_override, mgmt, lang_override]
                ).to_pandas()
                summary = translated["T_SUMMARY"].iloc[0]
                mgmt = translated["T_MGMT"].iloc[0]

            st.markdown(f"**What this means:** {summary}")
            st.markdown(f"**What to do:** {mgmt}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Possible alternative for {alert['DRUG_A_NAME']}:** {alert['ALTERNATIVE_FOR_A']}")
            with col2:
                st.markdown(f"**Possible alternative for {alert['DRUG_B_NAME']}:** {alert['ALTERNATIVE_FOR_B']}")

            st.caption("Always consult your healthcare provider before making any changes.")
            st.caption("Drug interaction data is AI-generated and not clinically validated.")
