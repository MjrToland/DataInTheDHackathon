"""
Drug Interaction Intelligence Platform
Landing page with role selection: Provider, Patient, or Admin (demo) mode.
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


def logout():
    for key in ["role", "provider_id", "provider_name", "patient_id", "patient_name", "patient_lang"]:
        st.session_state.pop(key, None)


def show_sidebar():
    role = st.session_state.get("role")
    st.sidebar.title("Drug Interaction Intelligence")
    st.sidebar.markdown("---")

    if role == "provider":
        st.sidebar.markdown(f"**Logged in as Provider**")
        st.sidebar.markdown(f"{st.session_state.get('provider_name', '')}")
    elif role == "patient":
        st.sidebar.markdown(f"**Logged in as Patient**")
        st.sidebar.markdown(f"{st.session_state.get('patient_name', '')}")
    elif role == "admin":
        st.sidebar.markdown("**Admin / Demo Mode**")

    if role:
        if st.sidebar.button("Log out"):
            logout()
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("**DataInTheD Hackathon 2026**")
    st.sidebar.caption("Cortex Agents | Semantic Views | Cortex Search | AI_TRANSLATE | Restricted Caller's Rights")


def show_login():
    st.title("Drug Interaction Intelligence Platform")
    st.markdown("AI-powered drug interaction detection and alerting for healthcare.")
    st.caption("Drug interaction data is AI-generated and not clinically validated.")
    st.markdown("---")

    col_prov, col_pat, col_admin = st.columns(3)

    # --- Provider login ---
    with col_prov:
        st.subheader("I'm a Provider")
        st.markdown("View your patient panel, flagged interactions, and sign up for email alerts.")

        providers = session.sql("""
            SELECT PROVIDER_ID,
                   FIRST_NAME || ' ' || LAST_NAME AS NAME,
                   SPECIALTY, CREDENTIAL
            FROM HEALTHCARE_DW.CORE.PROVIDERS
            WHERE STATUS = 'ACTIVE'
            ORDER BY LAST_NAME
        """).to_pandas()

        display_list = (providers["NAME"] + " (" + providers["SPECIALTY"] + ")").tolist()
        selected_idx = st.selectbox("Find your name", range(len(display_list)),
                                    format_func=lambda i: display_list[i],
                                    key="prov_select")

        if st.button("Sign in as Provider", type="primary", key="btn_prov"):
            row = providers.iloc[selected_idx]
            st.session_state["role"] = "provider"
            st.session_state["provider_id"] = int(row["PROVIDER_ID"])
            st.session_state["provider_name"] = row["NAME"]
            st.rerun()

    # --- Patient login ---
    with col_pat:
        st.subheader("I'm a Patient")
        st.markdown("View your medications and safety information in your language.")

        last_name = st.text_input("Last Name", key="pat_last")
        dob = st.date_input("Date of Birth", value=None, key="pat_dob")

        if st.button("Sign in as Patient", type="primary", key="btn_pat"):
            if last_name and dob:
                patients = session.sql(
                    """SELECT p.PATIENT_ID, p.FIRST_NAME, p.LAST_NAME,
                              COALESCE(pp.PREFERRED_LANGUAGE, 'en') AS PREFERRED_LANGUAGE
                       FROM HEALTHCARE_DW.CORE.PATIENTS p
                       LEFT JOIN HEALTHCARE_DW.DDI_APP.PATIENT_PREFERENCES pp
                         ON p.PATIENT_ID = pp.PATIENT_ID
                       WHERE UPPER(p.LAST_NAME) = UPPER(?)
                         AND p.DATE_OF_BIRTH = ?""",
                    params=[last_name, str(dob)]
                ).to_pandas()

                if patients.empty:
                    st.error("No patient found with that name and date of birth.")
                else:
                    row = patients.iloc[0]
                    st.session_state["role"] = "patient"
                    st.session_state["patient_id"] = int(row["PATIENT_ID"])
                    st.session_state["patient_name"] = f"{row['FIRST_NAME']} {row['LAST_NAME']}"
                    st.session_state["patient_lang"] = row["PREFERRED_LANGUAGE"]
                    st.rerun()
            else:
                st.warning("Enter both last name and date of birth.")

    # --- Admin / demo mode ---
    with col_admin:
        st.subheader("Demo / Admin")
        st.markdown("Full access to all pages and features. For judges and demos.")

        if st.button("Enter Admin Mode", key="btn_admin"):
            st.session_state["role"] = "admin"
            st.rerun()


def show_dashboard():
    role = st.session_state.get("role")

    st.title("Drug Interaction Intelligence Platform")
    st.caption("Drug interaction data is AI-generated and not clinically validated.")

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        result = session.sql("""
            SELECT COUNT(DISTINCT PATIENT_ID)
            FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS WHERE STATUS = 'FILLED'
        """).collect()
        st.metric("Patients on Meds", f"{result[0][0]:,}")

    with col2:
        result = session.sql("""
            SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.DRUG_INTERACTIONS
            WHERE SEVERITY IN ('CRITICAL', 'HIGH')
        """).collect()
        st.metric("High-Risk Interactions", f"{result[0][0]:,}")

    with col3:
        result = session.sql("""
            SELECT COUNT(DISTINCT PATIENT_ID)
            FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
            WHERE SEVERITY IN ('CRITICAL', 'HIGH')
        """).collect()
        st.metric("Patients at Risk", f"{result[0][0]:,}")

    with col4:
        result = session.sql("""
            SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG
        """).collect()
        st.metric("Alerts Drafted", f"{result[0][0]:,}")

    st.markdown("---")

    # Severity distribution
    st.subheader("Interaction Severity Distribution")
    severity_df = session.sql("""
        SELECT SEVERITY, COUNT(*) AS COUNT
        FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
        GROUP BY SEVERITY
        ORDER BY CASE SEVERITY
            WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
            WHEN 'MODERATE' THEN 3 ELSE 4 END
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
        FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS
        WHERE SEVERITY IN ('CRITICAL', 'HIGH')
        GROUP BY DRUG_A_NAME, DRUG_B_NAME, SEVERITY, CLINICAL_EFFECT
        ORDER BY AFFECTED_PATIENTS DESC
        LIMIT 10
    """).to_pandas()

    if not top_pairs.empty:
        st.dataframe(top_pairs, use_container_width=True, hide_index=True)

    # Navigation hints based on role
    st.markdown("---")
    if role == "provider":
        st.info("Use the sidebar to navigate to your **Provider Dashboard**, **Chat**, or **Inbox Triage**.")
    elif role == "patient":
        st.info("Use the sidebar to navigate to your **Patient Portal** or **Chat**.")
    elif role == "admin":
        st.info("Admin mode: all pages are accessible from the sidebar.")


# --- Main ---
show_sidebar()

if st.session_state.get("role"):
    show_dashboard()
else:
    show_login()
