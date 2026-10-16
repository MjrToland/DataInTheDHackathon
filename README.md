# Drug Interaction Intelligence Platform

**DataInTheD Hackathon 2026** — AI-powered drug interaction detection and alerting, built entirely on Snowflake.

## The Problem

As healthcare becomes more decentralized — with patients visiting urgent cares, telehealth providers, and specialists who don't share the same EHR — dangerous drug interactions slip through the cracks. A patient might get an SSRI from their psychiatrist and an NSAID from an urgent care, and nobody catches the bleeding risk. Providers managing large panels can't manually cross-reference every prescription combination. Current systems are reactive. We built a proactive one.

## What It Does

A Snowflake-native platform that:

1. **Detects** dangerous drug interactions by cross-referencing 60K patients' active prescriptions against 1,079 known interaction pairs, flagging CRITICAL, HIGH, MODERATE, and LOW severity
2. **Alerts** providers via AI-generated email drafts when high-severity interactions are found in their patient panel, with a self-service sign-up for email notifications
3. **Empowers** patients and providers with a multilingual AI chat interface — grounded in a searchable drug interaction knowledge base — to ask natural-language questions about their medications
4. **Checks** new drugs before prescribing, showing a provider (or patient) every known interaction between a candidate drug and the patient's current medications

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Streamlit Application (SiS)                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────┐ │
│  │   Provider    │ │   Patient    │ │   Chat   │ │Interaction│ │
│  │  Dashboard    │ │   Portal     │ │(Search + │ │  Checker  │ │
│  │              │ │ (translated) │ │AI_COMPLETE│ │           │ │
│  └──────┬───────┘ └──────┬───────┘ └────┬─────┘ └─────┬─────┘ │
│         │          AI_TRANSLATE         │              │       │
└─────────┼────────────────┼──────────────┼──────────────┼───────┘
          │                │              │              │
   ┌──────▼────────────────▼──────────────▼──────────────▼──────┐
   │              Cortex Agent + Tools                          │
   │   ┌─────────────────┐  ┌──────────────────────┐           │
   │   │  Semantic Views  │  │   Cortex Search      │           │
   │   │  (3 views for    │  │   (Drug Interactions │           │
   │   │   Analyst)       │  │    + Pharmacist Notes)│           │
   │   └────────┬─────────┘  └──────────┬───────────┘           │
   └────────────┼───────────────────────┼───────────────────────┘
                │                       │
   ┌────────────▼───────────────────────▼───────────────────────┐
   │              HEALTHCARE_DW + DDI_APP                        │
   │  ┌──────────┐ ┌───────────┐ ┌──────────────────────────┐  │
   │  │ 60K      │ │ 154K      │ │ 1,079 Drug Interactions  │  │
   │  │ Patients │ │ Prescrip- │ │ (AI-generated, 70 drugs) │  │
   │  │ 5K Provs │ │ tions     │ │ + Extended Lookup        │  │
   │  └──────────┘ └───────────┘ └──────────────────────────┘  │
   └──────────────────────┬─────────────────────────────────────┘
                          │
              ┌───────────▼────────────┐
              │  Email Alert Pipeline  │
              │  (Task + AI_COMPLETE   │
              │   draft generation)    │
              └────────────────────────┘
```

## Snowflake Features Used

| Feature | How We Used It |
|---|---|
| **Streamlit in Snowflake** | Single-page app with role-based navigation: Provider Dashboard, Patient Portal, AI Chat, and Interaction Checker. Role-gated views — providers and patients only see their own data. |
| **Cortex Agents** | Agent object wired to 3 semantic views + 2 Cortex Search services. Chat interface uses Cortex Search + AI_COMPLETE to ground answers in our drug interaction knowledge base. |
| **Semantic Views** | 3 views with full `TABLES / RELATIONSHIPS / DIMENSIONS / METRICS` DDL: patient medications, drug interaction alerts, and clinical encounters. Verified with Cortex Analyst. |
| **Cortex Search** | 2 search services: drug interaction knowledge base (175 entries) and pharmacist notes (154K prescriptions). Powers the chat's RAG pipeline via `SEARCH_PREVIEW`. |
| **AI_TRANSLATE** | Full-page translation on patient-facing views — titles, labels, alert summaries, management recommendations, and chat responses — in 9 languages. Language selector in sidebar. |
| **Restricted Caller's Rights** | 3 stored procedures (`EXECUTE AS RESTRICTED CALLER`) with proper `GRANT CALLER` / `GRANT INHERITED CALLER`. End users call procedures; they have no direct table SELECT. |

## Additional Features

| Feature | Description |
|---|---|
| **Drug Interaction Checker** | Before prescribing, check any drug against a patient's current medications or compare any two drugs. 70 drugs, 1,079 interaction pairs. |
| **Provider Email Sign-up** | Providers self-register for email alerts from within the dashboard. Subscription stored in `PROVIDER_EMAIL_SUBSCRIPTIONS`. |
| **AI-Generated Email Drafts** | Scheduled task generates professional alert emails for CRITICAL/HIGH interactions using AI_COMPLETE, stored in `ALERT_EMAIL_LOG`. |
| **Role-Based Personalization** | Home page shows personalized metrics. Providers see their patient panel stats. Patients see their own medication count and alerts. |
| **Parameterized SQL** | All user input is parameterized (`params=[]`). No SQL injection risk. |

## Setup

All objects are created in `HEALTHCARE_DW.DDI_APP`. Source tables in `HEALTHCARE_DW` are never modified.

Run the SQL scripts in `setup/` in order:

```
setup/02_data_enrichment.sql    -- Patient preferences, drug interactions, alerts view
setup/03_semantic_views.sql     -- 3 semantic views
setup/04_cortex_search.sql      -- 2 Cortex Search services
setup/05_cortex_agent.sql       -- Cortex Agent
setup/06_security.sql           -- RCR procedures, roles, caller grants
setup/07_email_pipeline.sql     -- Alert generation procedure + scheduled task
```

Then deploy the Streamlit app from `streamlit_app/` to `@HEALTHCARE_DW.DDI_APP.STREAMLIT_STAGE`.

## Project Structure

```
DataInTheDHackathon/
├── README.md
├── halfbaked.md                           # Transparency log: what's real, what's synthetic
├── setup/                                 # SQL scripts (run in order)
├── streamlit_app/
│   ├── app.py                             # Single entry point: login + role-based router
│   ├── views/
│   │   ├── provider_dashboard.py
│   │   ├── patient_portal.py
│   │   ├── chat.py
│   │   └── interaction_checker.py
│   └── utils/
│       ├── sidebar.py                     # Shared sidebar: user info, logout, language
│       ├── agent_client.py
│       └── translate.py
└── docs/
    ├── data_pipeline.md
    └── judging_criteria_map.md
```

## Built With

- **Snowflake Cortex**: AI_COMPLETE, AI_TRANSLATE, Cortex Search, Cortex Agents, Semantic Views
- **Snowflake CoCo**: Used throughout development — wrote and ran all SQL scripts, generated the drug interaction data, built and debugged the Streamlit app, managed deployments
- **Streamlit in Snowflake**: Container runtime deployment
- **claude-sonnet-4-6**: Powers interaction generation, email drafts, and chat responses

## Team

Built at DataInTheD Hackathon 2026.
