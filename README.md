# Drug Interaction Intelligence Platform

**DataInTheD Hackathon 2026** — AI-powered drug interaction detection, alerting, and self-service insights for healthcare providers and patients.

## Problem

Patients on multiple medications face risks from dangerous drug interactions that often go undetected until an adverse event occurs. Providers managing large panels can't manually cross-reference every prescription combination. Current systems are reactive, not proactive.

## Solution

A Snowflake-native intelligence platform that:

1. **Detects** dangerous drug interactions by cross-referencing patient prescriptions against DrugBank and FDA FAERS adverse event data from the Snowflake Marketplace
2. **Alerts** providers via automated email when high-severity interactions are identified in their patient panel
3. **Empowers** patients and providers with a multilingual AI chat interface to ask questions about their medications in their preferred language
4. **Triages** interaction alerts by severity, removing manual review from provider inboxes

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Application                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Provider  │ │ Patient  │ │   Chat   │ │    Inbox      │  │
│  │Dashboard  │ │ Portal   │ │Interface │ │   Triage      │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  │
│       │             │            │               │           │
│       │        AI_TRANSLATE      │               │           │
└───────┼─────────────┼────────────┼───────────────┼───────────┘
        │             │            │               │
   ┌────▼─────────────▼────────────▼───────────────▼────┐
   │              Cortex Agent                           │
   │   ┌─────────────────┐  ┌──────────────────────┐    │
   │   │  Semantic Views  │  │   Cortex Search      │    │
   │   │  (Analyst)       │  │   (Drug Interactions │    │
   │   │                  │  │    + Rx Notes)        │    │
   │   └────────┬─────────┘  └──────────┬───────────┘    │
   └────────────┼───────────────────────┼────────────────┘
                │                       │
   ┌────────────▼───────────────────────▼────────────────┐
   │              HEALTHCARE_DW                           │
   │  ┌──────────┐ ┌───────────┐ ┌───────────────────┐   │
   │  │ Patients │ │Prescrip-  │ │ Drug Interactions │   │
   │  │Providers │ │tions/Meds │ │ (Marketplace +    │   │
   │  │Encounters│ │           │ │  AI-enriched)     │   │
   │  └──────────┘ └───────────┘ └───────────────────┘   │
   └──────────────────────┬──────────────────────────────┘
                          │
              ┌───────────▼────────────┐
              │   Email Alert Pipeline │
              │   (Task + Notification │
              │    Integration)        │
              └────────────────────────┘
```

## Data Sources

| Source | Type | Purpose |
|---|---|---|
| `HEALTHCARE_DW` | Internal | Patient, prescription, encounter, diagnosis data (60K patients, 154K prescriptions) |
| DrugBank Biomedical Knowledge | Snowflake Marketplace | Drug-drug interaction pairs, severity, mechanism |
| FDA FAERS Adverse Events | Snowflake Marketplace | Real-world adverse event reports (5.6M+ cases) |

## Snowflake Features Used

| Feature | Usage |
|---|---|
| **Streamlit in Snowflake** | Multi-page app: provider dashboard, patient portal, chat, inbox triage |
| **Cortex Agents** | Chat backend for natural-language medication questions |
| **Semantic Views** | Structured access to healthcare data for Cortex Analyst |
| **Cortex Search** | Semantic search over drug interactions and pharmacist notes |
| **AI_TRANSLATE** | All patient-facing output translated to preferred language |
| **Restricted Caller's Rights** | App procedures run with elevated privileges; end users stay restricted |

## Setup

Run the SQL scripts in `setup/` in order:

```bash
# 1. Install Marketplace listings and set up interaction reference data
snowsql -f setup/01_marketplace_install.sql
snowsql -f setup/02_data_enrichment.sql

# 3. Create semantic views and search service
snowsql -f setup/03_semantic_views.sql
snowsql -f setup/04_cortex_search.sql

# 4. Create Cortex Agent
snowsql -f setup/05_cortex_agent.sql

# 5. Set up security model
snowsql -f setup/06_security.sql

# 6. Set up email alerting
snowsql -f setup/07_email_pipeline.sql
```

Then deploy the Streamlit app from `streamlit_app/`.

## Team

Built at DataInTheD Hackathon 2026.
