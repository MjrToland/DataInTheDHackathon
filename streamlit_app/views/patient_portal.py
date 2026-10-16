"""Patient Portal view."""
import streamlit as st
from utils.sidebar import translate


def render(session, lang):
    role = st.session_state.get("role")
    pid = st.session_state.get("patient_id")
    patient_name = st.session_state.get("patient_name", "")

    if role == "patient" and pid:
        st.title(translate("Patient Portal", lang, session))
        st.markdown(f"### {translate('Welcome', lang, session)}, {patient_name}")
    elif role == "admin":
        st.title("Patient Portal (Admin)")
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
                return
            row = patients.iloc[0]
            pid = int(row["PATIENT_ID"])
            patient_name = f"{row['FIRST_NAME']} {row['LAST_NAME']}"
            st.markdown(f"### {patient_name}")
        else:
            return
    else:
        st.error("This page is for patients.")
        return

    st.caption(translate("Drug interaction data is AI-generated and not clinically validated.", lang, session))
    st.markdown("---")

    # Current medications
    st.subheader(translate("Your Current Medications", lang, session))
    meds = session.sql(
        """SELECT rx.MEDICATION_NAME, m.DRUG_CLASS, rx.DOSAGE, rx.FREQUENCY,
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
        st.dataframe(meds, use_container_width=True)
    else:
        st.info(translate("No active medications found.", lang, session))

    st.markdown("---")
    st.subheader(translate("Safety Alerts", lang, session))
    alerts = session.sql(
        """SELECT INTERACTION_ID, DRUG_A_NAME, DRUG_B_NAME, SEVERITY,
                  PATIENT_SUMMARY, MANAGEMENT, ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
        FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
        WHERE PATIENT_ID = ?
        ORDER BY CASE SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MODERATE' THEN 3 ELSE 4 END""",
        params=[pid]
    ).to_pandas()

    if alerts.empty:
        st.success(translate("No drug interaction alerts for your current medications.", lang, session))
    else:
        st.warning(translate(f"{len(alerts)} interaction(s) detected in your current medications.", lang, session))
        lbl_what = translate("What this means", lang, session)
        lbl_todo = translate("What to do", lang, session)
        lbl_alt = translate("Possible alternative for", lang, session)

        for _, alert in alerts.iterrows():
            sev = alert["SEVERITY"]
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            with st.expander(f"{icon} {sev}: {alert['DRUG_A_NAME']} + {alert['DRUG_B_NAME']}"):
                summary = translate(alert["PATIENT_SUMMARY"] or "", lang, session)
                mgmt = translate(alert["MANAGEMENT"] or "", lang, session)
                st.markdown(f"**{lbl_what}:** {summary}")
                st.markdown(f"**{lbl_todo}:** {mgmt}")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**{lbl_alt} {alert['DRUG_A_NAME']}:** {translate(alert['ALTERNATIVE_FOR_A'] or '', lang, session)}")
                with col2:
                    st.markdown(f"**{lbl_alt} {alert['DRUG_B_NAME']}:** {translate(alert['ALTERNATIVE_FOR_B'] or '', lang, session)}")
                st.caption(translate("Always consult your healthcare provider before making any changes.", lang, session))
