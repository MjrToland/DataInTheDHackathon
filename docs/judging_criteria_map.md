# Judging Criteria Mapping

## Required Features

| Judging Criteria | Where Implemented | Details |
|---|---|---|
| **Streamlit** | `streamlit_app/app.py` + `views/` | Single-page app with role-based navigation. 4 views: Provider Dashboard, Patient Portal, Chat, Interaction Checker. Deployed to SiS container runtime. |
| **Cortex Agents** | `setup/05_cortex_agent.sql`, `views/chat.py` | Agent object configured with 3 semantic views + 2 Cortex Search services. Chat uses Cortex Search (SEARCH_PREVIEW) + AI_COMPLETE for grounded, data-aware answers. |
| **Semantic Views** | `setup/03_semantic_views.sql` | 3 semantic views with real TABLES/RELATIONSHIPS/DIMENSIONS/METRICS DDL: `SV_PATIENT_MEDICATIONS`, `SV_DRUG_INTERACTION_ALERTS`, `SV_PATIENT_ENCOUNTERS`. Verified with Cortex Analyst. |
| **Cortex Search** | `setup/04_cortex_search.sql` | 2 search services: drug interactions (175 entries, severity/drug filtering) and pharmacist notes (154K entries). Queried via `SEARCH_PREVIEW` in the chat. |
| **AI_TRANSLATE** | `views/patient_portal.py`, `views/chat.py`, `views/interaction_checker.py` | Full-page translation: titles, labels, alert summaries, management recs, and chat responses. 9 languages. Sidebar language selector. |
| **Restricted Caller's Rights** | `setup/06_security.sql` | 3 procedures with `EXECUTE AS RESTRICTED CALLER`. Owned by `DRUG_INTERACTION_APP_ROLE` with `GRANT CALLER` / `GRANT INHERITED CALLER`. End-user role has USAGE on procedures, no direct table SELECT. |

## Suggested Feature Ideas

| Suggestion | Where Implemented | Details |
|---|---|---|
| **Chat interface for Q&A** | `views/chat.py` | Conversational chat grounded in Cortex Search drug interaction data. Adapts tone for patients (plain language) vs. providers (clinical). Supports multilingual responses. |
| **Personalized view per user** | `app.py`, `views/provider_dashboard.py`, `views/patient_portal.py` | Role-based login (provider/patient/admin). Home page shows personalized metrics. Providers see their panel. Patients see their own meds and alerts. |
| **Answers in user's language** | `views/patient_portal.py`, `views/chat.py`, `views/interaction_checker.py` | Full-page AI_TRANSLATE in 9 languages. Chat tells the LLM to respond in the selected language. |
| **Self-service tool** | `views/provider_dashboard.py` (email sign-up), `views/interaction_checker.py` | Providers sign up for email alerts from the dashboard. Interaction checker lets anyone check a drug before prescribing. |

## Project Structure

```
DataInTheDHackathon/
├── README.md
├── halfbaked.md
├── setup/
│   ├── 02_data_enrichment.sql
│   ├── 03_semantic_views.sql
│   ├── 04_cortex_search.sql
│   ├── 05_cortex_agent.sql
│   ├── 06_security.sql
│   └── 07_email_pipeline.sql
├── streamlit_app/
│   ├── app.py                             # Entry point: login + role-based router
│   ├── views/
│   │   ├── provider_dashboard.py
│   │   ├── patient_portal.py
│   │   ├── chat.py
│   │   └── interaction_checker.py
│   └── utils/
│       ├── sidebar.py
│       ├── agent_client.py
│       └── translate.py
└── docs/
    ├── data_pipeline.md
    └── judging_criteria_map.md
```
