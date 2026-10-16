"""
Patient Portal — Personalized view for each patient showing their current
medications, flagged interactions, and translated summaries in their language.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Patient Portal", page_icon="👤", layout="wide")
session = get_active_session()

st.title("Patient Portal")
st.markdown("View your medications and safety information in your language.")

# Patient lookup
search_col1, search_col2 = st.columns(2)
with search_col1:
    last_name = st.text_input("Last Name")
with search_col2:
    dob = st.date_input("Date of Birth", value=None)

if last_name and dob:
    patients = session.sql(f"""
        SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, DATE_OF_BIRTH, PREFERRED_LANGUAGE
        FROM HEALTHCARE_DW.CORE.PATIENTS
        WHERE UPPER(LAST_NAME) = UPPER('{last_name.replace("'", "''")}')
          AND DATE_OF_BIRTH = '{dob}'
    """).to_pandas()

    if patients.empty:
        st.warning("No patient found with that name and date of birth.")
    else:
        patient = patients.iloc[0]
        pid = int(patient["PATIENT_ID"])
        lang = patient["PREFERRED_LANGUAGE"]

        LANG_NAMES = {
            "en": "English", "es": "Spanish", "ar": "Arabic", "zh": "Chinese",
            "fr": "French", "pt": "Portuguese", "de": "German", "ko": "Korean",
            "vi": "Vietnamese", "ja": "Japanese"
        }

        st.markdown(f"### Welcome, {patient['FIRST_NAME']} {patient['LAST_NAME']}")
        st.markdown(f"**Language preference:** {LANG_NAMES.get(lang, lang)}")

        lang_override = st.selectbox(
            "Display language",
            list(LANG_NAMES.keys()),
            format_func=lambda x: LANG_NAMES[x],
            index=list(LANG_NAMES.keys()).index(lang) if lang in LANG_NAMES else 0
        )

        st.markdown("---")

        # Current medications
        st.subheader("Your Current Medications")
        meds = session.sql(f"""
            SELECT
                rx.MEDICATION_NAME,
                m.DRUG_CLASS,
                rx.DOSAGE,
                rx.FREQUENCY,
                rx.PRESCRIBED_DATE,
                rx.REFILLS_REMAINING,
                prov.FIRST_NAME || ' ' || prov.LAST_NAME AS PRESCRIBER
            FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx
            JOIN HEALTHCARE_DW.PHARMACY.MEDICATIONS m ON rx.MEDICATION_ID = m.MEDICATION_ID
            LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov ON rx.PROVIDER_ID = prov.PROVIDER_ID
            WHERE rx.PATIENT_ID = {pid}
              AND rx.STATUS IN ('ACTIVE', 'FILLED')
            QUALIFY ROW_NUMBER() OVER (PARTITION BY rx.MEDICATION_ID ORDER BY rx.PRESCRIBED_DATE DESC) = 1
            ORDER BY rx.MEDICATION_NAME
        """).to_pandas()

        if not meds.empty:
            st.dataframe(meds, use_container_width=True, hide_index=True)
        else:
            st.info("No active medications found.")

        st.markdown("---")

        # Drug interaction alerts with translation
        st.subheader("Safety Alerts")
        alerts = session.sql(f"""
            SELECT
                INTERACTION_ID,
                DRUG_A_NAME,
                DRUG_B_NAME,
                SEVERITY,
                PATIENT_SUMMARY,
                MANAGEMENT,
                ALTERNATIVE_FOR_A,
                ALTERNATIVE_FOR_B
            FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
            WHERE PATIENT_ID = {pid}
            ORDER BY
                CASE SEVERITY
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MODERATE' THEN 3 ELSE 4
                END
        """).to_pandas()

        if alerts.empty:
            st.success("No drug interaction alerts for your current medications.")
        else:
            st.warning(f"**{len(alerts)} interaction(s) detected** in your current medications.")

            for _, alert in alerts.iterrows():
                sev = alert["SEVERITY"]
                icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")

                with st.expander(f"{icon} {sev}: {alert['DRUG_A_NAME']} + {alert['DRUG_B_NAME']}"):
                    summary = alert["PATIENT_SUMMARY"]
                    mgmt = alert["MANAGEMENT"]

                    # Translate if needed
                    if lang_override != "en" and summary:
                        translated = session.sql(f"""
                            SELECT
                                SNOWFLAKE.CORTEX.TRANSLATE('{summary.replace("'", "''")}', 'en', '{lang_override}') AS T_SUMMARY,
                                SNOWFLAKE.CORTEX.TRANSLATE('{mgmt.replace("'", "''")}', 'en', '{lang_override}') AS T_MGMT
                        """).to_pandas()
                        summary = translated["T_SUMMARY"].iloc[0]
                        mgmt = translated["T_MGMT"].iloc[0]

                    st.markdown(f"**What this means:** {summary}")
                    st.markdown(f"**What to do:** {mgmt}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Possible alternative for {alert['DRUG_A_NAME']}:** {alert['ALTERNATIVE_FOR_A']}")
                    with col2:
                        st.markdown(f"**Possible alternative for {alert['DRUG_B_NAME']}:** {alert['ALTERNATIVE_FOR_B']}")

                    st.caption("Always consult your healthcare provider before making any changes to your medications.")
