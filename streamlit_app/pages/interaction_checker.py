"""
Drug Interaction Checker — Look up interactions for any drug against
the patient's current medications or the full formulary.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session
from utils.sidebar import render_sidebar, translate

st.set_page_config(page_title="Interaction Checker", page_icon="🔍", layout="wide")
session = get_active_session()
lang = render_sidebar(session, show_language=True)

role = st.session_state.get("role")
if not role:
    st.warning("Please sign in from the home page.")
    st.stop()

st.title(translate("Drug Interaction Checker", lang, session))
st.markdown(translate("Check if a medication you're considering interacts with current prescriptions or other drugs.", lang, session))
st.caption(translate("All interaction data is AI-generated and not clinically validated. Always consult a provider.", lang, session))

all_drugs = session.sql("""
    SELECT GENERIC_NAME, DRUG_CLASS FROM HEALTHCARE_DW.PHARMACY.MEDICATIONS
    UNION
    SELECT GENERIC_NAME, DRUG_CLASS FROM HEALTHCARE_DW.DDI_APP.EXTENDED_DRUG_LOOKUP
    ORDER BY GENERIC_NAME
""").to_pandas()

drug_display = (all_drugs["GENERIC_NAME"] + " (" + all_drugs["DRUG_CLASS"] + ")").tolist()

st.markdown("---")

lbl_tab1 = translate("Check Against My Medications", lang, session)
lbl_tab2 = translate("Check Any Two Drugs", lang, session)
tab_patient, tab_any = st.tabs([lbl_tab1, lbl_tab2])

with tab_patient:
    pid = st.session_state.get("patient_id")

    if role == "patient" and pid:
        st.markdown(translate(f"Checking against **{st.session_state.get('patient_name', '')}'s** current medications.", lang, session))
    elif role in ("admin", "provider"):
        patient_list = session.sql("""
            SELECT PATIENT_ID,
                   FIRST_NAME || ' ' || LAST_NAME AS NAME,
                   DATE_OF_BIRTH
            FROM HEALTHCARE_DW.CORE.PATIENTS
            ORDER BY LAST_NAME
            LIMIT 200
        """).to_pandas()
        pat_display = (patient_list["NAME"] + " (DOB: " + patient_list["DATE_OF_BIRTH"].astype(str) + ")").tolist()
        pat_idx = st.selectbox(translate("Select a patient", lang, session), range(len(pat_display)),
                               format_func=lambda i: pat_display[i],
                               key="checker_pat_select")
        pid = int(patient_list.iloc[pat_idx]["PATIENT_ID"])
    else:
        pid = None

    if pid:
        current_meds = session.sql(
            """SELECT DISTINCT rx.MEDICATION_NAME
               FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx
               WHERE rx.PATIENT_ID = ? AND rx.STATUS = 'FILLED'""",
            params=[pid]
        ).to_pandas()

        if current_meds.empty:
            st.info(translate("No active medications found for this patient.", lang, session))
        else:
            st.markdown(f"**{translate('Current medications', lang, session)}:** {', '.join(current_meds['MEDICATION_NAME'].tolist())}")
            st.markdown("---")

            selected_idx = st.selectbox(
                translate("Select a drug to check for interactions", lang, session),
                range(len(drug_display)),
                format_func=lambda i: drug_display[i],
                key="check_drug_patient"
            )
            check_drug = all_drugs.iloc[selected_idx]["GENERIC_NAME"]

            if st.button(translate("Check Interactions", lang, session), type="primary", key="btn_check_patient"):
                med_list = current_meds["MEDICATION_NAME"].tolist()
                placeholders = ", ".join(["?"] * len(med_list))
                params = [check_drug] + med_list + [check_drug] + med_list

                results = session.sql(
                    f"""SELECT DRUG_A_NAME, DRUG_B_NAME, SEVERITY, CLINICAL_EFFECT,
                               MANAGEMENT, PATIENT_SUMMARY, ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
                        FROM HEALTHCARE_DW.DDI_APP.EXTENDED_DRUG_INTERACTIONS
                        WHERE (DRUG_A_NAME = ? AND DRUG_B_NAME IN ({placeholders}))
                           OR (DRUG_B_NAME = ? AND DRUG_A_NAME IN ({placeholders}))
                        ORDER BY CASE SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                                 WHEN 'MODERATE' THEN 3 ELSE 4 END""",
                    params=params
                ).to_pandas()

                if results.empty:
                    st.success(translate(f"No known interactions between {check_drug} and your current medications.", lang, session))
                else:
                    st.warning(translate(f"{len(results)} interaction(s) found between {check_drug} and your current medications.", lang, session))
                    for _, r in results.iterrows():
                        sev = r["SEVERITY"]
                        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                        other_drug = r["DRUG_B_NAME"] if r["DRUG_A_NAME"] == check_drug else r["DRUG_A_NAME"]
                        with st.expander(f"{icon} {sev}: {check_drug} + {other_drug}"):
                            st.markdown(f"**{translate('Clinical Effect', lang, session)}:** {translate(r['CLINICAL_EFFECT'], lang, session)}")
                            st.markdown(f"**{translate('Management', lang, session)}:** {translate(r['MANAGEMENT'], lang, session)}")
                            st.markdown(f"**{translate('Patient Summary', lang, session)}:** {translate(r['PATIENT_SUMMARY'], lang, session)}")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**{translate('Alternative for', lang, session)} {r['DRUG_A_NAME']}:** {translate(r['ALTERNATIVE_FOR_A'], lang, session)}")
                            with col2:
                                st.markdown(f"**{translate('Alternative for', lang, session)} {r['DRUG_B_NAME']}:** {translate(r['ALTERNATIVE_FOR_B'], lang, session)}")
                            st.caption(translate("AI-generated. Not clinically validated.", lang, session))

with tab_any:
    st.markdown(translate("Check the interaction between any two drugs in our knowledge base.", lang, session))

    col1, col2 = st.columns(2)
    with col1:
        idx_a = st.selectbox(translate("Drug A", lang, session), range(len(drug_display)),
                             format_func=lambda i: drug_display[i], key="drug_a")
    with col2:
        idx_b = st.selectbox(translate("Drug B", lang, session), range(len(drug_display)),
                             format_func=lambda i: drug_display[i], key="drug_b",
                             index=min(1, len(drug_display) - 1))

    drug_a = all_drugs.iloc[idx_a]["GENERIC_NAME"]
    drug_b = all_drugs.iloc[idx_b]["GENERIC_NAME"]

    if drug_a == drug_b:
        st.warning(translate("Select two different drugs.", lang, session))
    elif st.button(translate("Check Interaction", lang, session), type="primary", key="btn_check_pair"):
        result = session.sql(
            """SELECT DRUG_A_NAME, DRUG_B_NAME, SEVERITY, INTERACTION_TYPE,
                      MECHANISM, CLINICAL_EFFECT, MANAGEMENT, PATIENT_SUMMARY,
                      ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B
               FROM HEALTHCARE_DW.DDI_APP.EXTENDED_DRUG_INTERACTIONS
               WHERE (DRUG_A_NAME = ? AND DRUG_B_NAME = ?)
                  OR (DRUG_A_NAME = ? AND DRUG_B_NAME = ?)""",
            params=[drug_a, drug_b, drug_b, drug_a]
        ).to_pandas()

        if result.empty:
            st.success(translate(f"No known interaction between {drug_a} and {drug_b} in our knowledge base.", lang, session))
        else:
            r = result.iloc[0]
            sev = r["SEVERITY"]
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            st.markdown(f"### {icon} {sev}: {drug_a} + {drug_b}")
            st.markdown(f"**{translate('Type', lang, session)}:** {translate(r['INTERACTION_TYPE'], lang, session)}")
            st.markdown(f"**{translate('Mechanism', lang, session)}:** {translate(r['MECHANISM'], lang, session)}")
            st.markdown(f"**{translate('Clinical Effect', lang, session)}:** {translate(r['CLINICAL_EFFECT'], lang, session)}")
            st.markdown(f"**{translate('Management', lang, session)}:** {translate(r['MANAGEMENT'], lang, session)}")
            st.markdown(f"**{translate('Patient Summary', lang, session)}:** {translate(r['PATIENT_SUMMARY'], lang, session)}")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{translate('Alternative for', lang, session)} {r['DRUG_A_NAME']}:** {translate(r['ALTERNATIVE_FOR_A'], lang, session)}")
            with col2:
                st.markdown(f"**{translate('Alternative for', lang, session)} {r['DRUG_B_NAME']}:** {translate(r['ALTERNATIVE_FOR_B'], lang, session)}")
            st.caption(translate("AI-generated. Not clinically validated.", lang, session))
