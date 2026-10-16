"""
Drug Interaction Intelligence Platform
Single-page app with role-based navigation. No pages/ directory --
the sidebar radio only shows pages the logged-in role can access.
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session
from utils.sidebar import render_sidebar, LANG_NAMES

st.set_page_config(
    page_title="Drug Interaction Intelligence",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

session = get_active_session()

# Role-based page map
PROVIDER_PAGES = ["Home", "Provider Dashboard", "Interaction Checker", "Chat"]
PATIENT_PAGES = ["Home", "Patient Portal", "Interaction Checker", "Chat"]
ADMIN_PAGES = ["Home", "Provider Dashboard", "Patient Portal", "Interaction Checker", "Chat"]


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def show_sidebar_nav():
    role = st.session_state.get("role")
    st.sidebar.title("Drug Interaction Intelligence")
    st.sidebar.markdown("---")

    if role == "provider":
        st.sidebar.markdown(f"**Provider**")
        st.sidebar.markdown(st.session_state.get("provider_name", ""))
    elif role == "patient":
        st.sidebar.markdown(f"**Patient**")
        st.sidebar.markdown(st.session_state.get("patient_name", ""))
    elif role == "admin":
        st.sidebar.markdown("**Admin / Demo Mode**")

    # Navigation radio -- only show pages for this role
    page_list = {"provider": PROVIDER_PAGES, "patient": PATIENT_PAGES, "admin": ADMIN_PAGES}.get(role, [])
    selected_page = None
    if page_list:
        selected_page = st.sidebar.radio("Navigate", page_list, key="nav_radio")

    if role:
        if st.sidebar.button("Log out"):
            logout()
            st.experimental_rerun()

    # Language selector
    lang = "en"
    if role in ("patient", "provider", "admin"):
        st.sidebar.markdown("---")
        default_lang = st.session_state.get("patient_lang", "en") if role == "patient" else "en"
        default_idx = list(LANG_NAMES.keys()).index(default_lang) if default_lang in LANG_NAMES else 0
        lang = st.sidebar.selectbox(
            "Language", list(LANG_NAMES.keys()),
            format_func=lambda x: LANG_NAMES[x],
            index=default_idx,
            key="sidebar_lang"
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**DataInTheD Hackathon 2026**")

    return selected_page, lang


# ============================================================
# Login page
# ============================================================
def show_login():
    st.title("Drug Interaction Intelligence Platform")
    st.markdown("AI-powered drug interaction detection and alerting for healthcare.")
    st.caption("Drug interaction data is AI-generated and not clinically validated.")
    st.markdown("---")

    col_prov, col_pat, col_admin = st.columns(3)

    with col_prov:
        st.subheader("I'm a Provider")
        st.markdown("View your patient panel, flagged interactions, and sign up for email alerts.")
        providers = session.sql("""
            SELECT PROVIDER_ID, FIRST_NAME || ' ' || LAST_NAME AS NAME, SPECIALTY
            FROM HEALTHCARE_DW.CORE.PROVIDERS WHERE STATUS = 'ACTIVE' ORDER BY LAST_NAME
        """).to_pandas()
        display_list = (providers["NAME"] + " (" + providers["SPECIALTY"] + ")").tolist()
        selected_idx = st.selectbox("Find your name", range(len(display_list)),
                                    format_func=lambda i: display_list[i], key="prov_select")
        if st.button("Sign in as Provider", type="primary", key="btn_prov"):
            row = providers.iloc[selected_idx]
            st.session_state["role"] = "provider"
            st.session_state["provider_id"] = int(row["PROVIDER_ID"])
            st.session_state["provider_name"] = row["NAME"]
            st.experimental_rerun()

    with col_pat:
        st.subheader("I'm a Patient")
        st.markdown("View your medications and safety information in your language.")
        if "suggested_patient" not in st.session_state:
            suggested = session.sql("""
                SELECT FIRST_NAME, LAST_NAME, DATE_OF_BIRTH
                FROM HEALTHCARE_DW.CORE.PATIENTS ORDER BY RANDOM() LIMIT 1
            """).to_pandas()
            if not suggested.empty:
                st.session_state["suggested_patient"] = {
                    "last_name": suggested.iloc[0]["LAST_NAME"],
                    "dob": str(suggested.iloc[0]["DATE_OF_BIRTH"]),
                    "first_name": suggested.iloc[0]["FIRST_NAME"],
                }
        hint = st.session_state.get("suggested_patient", {})
        if hint:
            st.info(f"Try: **{hint.get('first_name', '')} {hint.get('last_name', '')}**, DOB **{hint.get('dob', '')}**")
        last_name = st.text_input("Last Name", value=hint.get("last_name", ""), key="pat_last")
        dob = st.date_input("Date of Birth", value=None, key="pat_dob")
        if st.button("Sign in as Patient", type="primary", key="btn_pat"):
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
                    st.error("No patient found with that name and date of birth.")
                else:
                    row = patients.iloc[0]
                    st.session_state["role"] = "patient"
                    st.session_state["patient_id"] = int(row["PATIENT_ID"])
                    st.session_state["patient_name"] = f"{row['FIRST_NAME']} {row['LAST_NAME']}"
                    st.session_state["patient_lang"] = row["PREFERRED_LANGUAGE"]
                    st.experimental_rerun()
            else:
                st.warning("Enter both last name and date of birth.")

    with col_admin:
        st.subheader("Demo / Admin")
        st.markdown("Full access to all pages and features.")
        if st.button("Enter Admin Mode", key="btn_admin"):
            st.session_state["role"] = "admin"
            st.experimental_rerun()


# ============================================================
# Home dashboard (personalized by role)
# ============================================================
def show_home(lang):
    role = st.session_state.get("role")
    st.title("Drug Interaction Intelligence Platform")
    st.caption("Drug interaction data is AI-generated and not clinically validated.")

    if role == "patient":
        pid = st.session_state.get("patient_id")
        st.markdown(f"### {st.session_state.get('patient_name', '')}")
        col1, col2 = st.columns(2)
        with col1:
            r = session.sql("SELECT COUNT(DISTINCT MEDICATION_ID) FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS WHERE PATIENT_ID = ? AND STATUS = 'FILLED'", params=[pid]).collect()
            st.metric("Your Medications", f"{r[0][0]:,}")
        with col2:
            r = session.sql("SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS WHERE PATIENT_ID = ? AND SEVERITY IN ('CRITICAL','HIGH')", params=[pid]).collect()
            st.metric("Interactions to Review", f"{r[0][0]:,}")
    elif role == "provider":
        provider_id = st.session_state.get("provider_id")
        st.markdown(f"### {st.session_state.get('provider_name', '')}")
        col1, col2, col3 = st.columns(3)
        with col1:
            r = session.sql("SELECT COUNT(DISTINCT PATIENT_ID) FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS WHERE PRESCRIBER_A_ID = ? OR PRESCRIBER_B_ID = ?", params=[provider_id, provider_id]).collect()
            st.metric("Your Patients at Risk", f"{r[0][0]:,}")
        with col2:
            r = session.sql("SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS WHERE (PRESCRIBER_A_ID = ? OR PRESCRIBER_B_ID = ?) AND SEVERITY IN ('CRITICAL','HIGH')", params=[provider_id, provider_id]).collect()
            st.metric("Critical/High Alerts", f"{r[0][0]:,}")
        with col3:
            r = session.sql("SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG WHERE PROVIDER_ID = ?", params=[provider_id]).collect()
            st.metric("Alerts Drafted", f"{r[0][0]:,}")
    else:
        # Admin global stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            r = session.sql("SELECT COUNT(DISTINCT PATIENT_ID) FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS WHERE STATUS = 'FILLED'").collect()
            st.metric("Patients on Meds", f"{r[0][0]:,}")
        with col2:
            r = session.sql("SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.DRUG_INTERACTIONS WHERE SEVERITY IN ('CRITICAL','HIGH')").collect()
            st.metric("High-Risk Interactions", f"{r[0][0]:,}")
        with col3:
            r = session.sql("SELECT COUNT(DISTINCT PATIENT_ID) FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS WHERE SEVERITY IN ('CRITICAL','HIGH')").collect()
            st.metric("Patients at Risk", f"{r[0][0]:,}")
        with col4:
            r = session.sql("SELECT COUNT(*) FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG").collect()
            st.metric("Alerts Drafted", f"{r[0][0]:,}")


# ============================================================
# Main routing
# ============================================================
role = st.session_state.get("role")

if not role:
    show_login()
else:
    page, lang = show_sidebar_nav()

    if page == "Home" or page is None:
        show_home(lang)
    elif page == "Provider Dashboard":
        from views.provider_dashboard import render
        render(session)
    elif page == "Patient Portal":
        from views.patient_portal import render
        render(session, lang)
    elif page == "Interaction Checker":
        from views.interaction_checker import render
        render(session, lang)
    elif page == "Chat":
        from views.chat import render
        render(session, lang)
