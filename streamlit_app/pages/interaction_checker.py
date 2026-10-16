"""
Drug Interaction Checker — Look up interactions for any drug against
the patient's current medications or the full formulary.
Works for providers and patients.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="Interaction Checker", page_icon="🔍", layout="wide")
session = get_active_session()

role = st.session_state.get("role")
if not role:
    st.warning("Please sign in from the home page.")
    st.stop()

st.title("Drug Interaction Checker")
st.markdown("Check if a medication you're considering interacts with current prescriptions or other drugs.")
st.caption("All interaction data is AI-generated and not clinically validated. Always consult a provider.")

# Build the drug list from both the original formulary and the extended lookup
all_drugs = session.sql("""
    SELECT GENERIC_NAME, DRUG_CLASS FROM HEALTHCARE_DW.PHARMACY.MEDICATIONS
    UNION
    SELECT GENERIC_NAME, DRUG_CLASS FROM HEALTHCARE_DW.DDI_APP.EXTENDED_DRUG_LOOKUP
    ORDER BY GENERIC_NAME
""").to_pandas()

drug_display = (all_drugs["GENERIC_NAME"] + " (" + all_drugs["DRUG_CLASS"] + ")").tolist()

st.markdown("---")

# Two modes: check against patient's meds, or check any pair
tab_patient, tab_any = st.tabs(["Check Against My Medications", "Check Any Two Drugs"])

with tab_patient:
    pid = st.session_state.get("patient_id")

    if role == "patient" and pid:
        st.markdown(f"Checking against **{st.session_state.get('patient_name', '')}'s** current medications.")
    elif role == "admin":
        lookup_pid = st.number_input("Patient ID", min_value=1, step=1, key="checker_pid")
        pid = int(lookup_pid) if lookup_pid else None
    elif role == "provider":
        lookup_pid = st.number_input("Patient ID", min_value=1, step=1, key="checker_pid_prov")
        pid = int(lookup_pid) if lookup_pid else None
    else:
        pid = None

    if pid:
        # Show current meds
        current_meds = session.sql(
            """SELECT DISTINCT rx.MEDICATION_NAME
               FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx
               WHERE rx.PATIENT_ID = ? AND rx.STATUS = 'FILLED'""",
            params=[pid]
        ).to_pandas()

        if current_meds.empty:
            st.info("No active medications found for this patient.")
        else:
            st.markdown(f"**Current medications:** {', '.join(current_meds['MEDICATION_NAME'].tolist())}")
            st.markdown("---")

            selected_idx = st.selectbox(
                "Select a drug to check for interactions",
                range(len(drug_display)),
                format_func=lambda i: drug_display[i],
                key="check_drug_patient"
            )
            check_drug = all_drugs.iloc[selected_idx]["GENERIC_NAME"]

            if st.button("Check Interactions", type="primary", key="btn_check_patient"):
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
                    st.success(f"No known interactions between **{check_drug}** and your current medications.")
                else:
                    st.warning(f"**{len(results)} interaction(s) found** between {check_drug} and your current medications.")
                    for _, r in results.iterrows():
                        sev = r["SEVERITY"]
                        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                        other_drug = r["DRUG_B_NAME"] if r["DRUG_A_NAME"] == check_drug else r["DRUG_A_NAME"]
                        with st.expander(f"{icon} {sev}: {check_drug} + {other_drug}"):
                            st.markdown(f"**Clinical Effect:** {r['CLINICAL_EFFECT']}")
                            st.markdown(f"**Management:** {r['MANAGEMENT']}")
                            st.markdown(f"**Patient Summary:** {r['PATIENT_SUMMARY']}")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Alternative for {r['DRUG_A_NAME']}:** {r['ALTERNATIVE_FOR_A']}")
                            with col2:
                                st.markdown(f"**Alternative for {r['DRUG_B_NAME']}:** {r['ALTERNATIVE_FOR_B']}")
                            st.caption("AI-generated. Not clinically validated.")

with tab_any:
    st.markdown("Check the interaction between any two drugs in our knowledge base.")

    col1, col2 = st.columns(2)
    with col1:
        idx_a = st.selectbox("Drug A", range(len(drug_display)),
                             format_func=lambda i: drug_display[i], key="drug_a")
    with col2:
        idx_b = st.selectbox("Drug B", range(len(drug_display)),
                             format_func=lambda i: drug_display[i], key="drug_b",
                             index=min(1, len(drug_display) - 1))

    drug_a = all_drugs.iloc[idx_a]["GENERIC_NAME"]
    drug_b = all_drugs.iloc[idx_b]["GENERIC_NAME"]

    if drug_a == drug_b:
        st.warning("Select two different drugs.")
    elif st.button("Check Interaction", type="primary", key="btn_check_pair"):
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
            st.success(f"No known interaction between **{drug_a}** and **{drug_b}** in our knowledge base.")
        else:
            r = result.iloc[0]
            sev = r["SEVERITY"]
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(sev, "⚪")
            st.markdown(f"### {icon} {sev} Interaction: {drug_a} + {drug_b}")
            st.markdown(f"**Type:** {r['INTERACTION_TYPE']}")
            st.markdown(f"**Mechanism:** {r['MECHANISM']}")
            st.markdown(f"**Clinical Effect:** {r['CLINICAL_EFFECT']}")
            st.markdown(f"**Management:** {r['MANAGEMENT']}")
            st.markdown(f"**Patient Summary:** {r['PATIENT_SUMMARY']}")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Alternative for {r['DRUG_A_NAME']}:** {r['ALTERNATIVE_FOR_A']}")
            with col2:
                st.markdown(f"**Alternative for {r['DRUG_B_NAME']}:** {r['ALTERNATIVE_FOR_B']}")
            st.caption("AI-generated. Not clinically validated.")
