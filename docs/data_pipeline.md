# Data Pipeline Documentation

## Pipeline Architecture

```
┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│ HEALTHCARE_DW    │    │  DATA ENRICHMENT    │    │  AI SERVICES     │
│ Source Tables     │───▶│  Pipeline           │───▶│  Layer           │
│                  │    │                     │    │                  │
│ • PATIENTS       │    │ • Cross-join med    │    │ • Cortex Search  │
│ • PRESCRIPTIONS  │    │   pairs (190)       │    │ • Cortex Agent   │
│ • MEDICATIONS    │    │ • AI_COMPLETE for   │    │ • Semantic Views │
│ • ENCOUNTERS     │    │   interaction data  │    │ • AI_TRANSLATE   │
│ • DIAGNOSES      │    │ • Polypharmacy view │    │                  │
│ • PROVIDERS      │    │ • Search corpus     │    │                  │
└──────────────────┘    └─────────────────────┘    └──────────────────┘
                                                           │
                               ┌───────────────────────────┤
                               ▼                           ▼
                    ┌──────────────────┐        ┌─────────────────┐
                    │  EMAIL PIPELINE  │        │  STREAMLIT APP  │
                    │                  │        │                 │
                    │ • Scheduled Task │        │ • Provider View │
                    │   (every 6 hrs)  │        │ • Patient View  │
                    │ • Detect new     │        │ • Chat (Agent)  │
                    │   interactions   │        │ • Inbox Triage  │
                    │ • Generate email │        │                 │
                    │ • Log to table   │        │                 │
                    └──────────────────┘        └─────────────────┘
```

## Pipeline Steps

### 1. Data Enrichment (`02_data_enrichment.sql`)

**Input:** `PHARMACY.MEDICATIONS` (20 drugs)

**Process:**
1. Add `PREFERRED_LANGUAGE` column to `CORE.PATIENTS` for multilingual support
2. Cross-join all medication pairs → 190 unique combinations
3. For each pair, call `CORTEX.AI_COMPLETE` (claude-3-5-sonnet) to generate:
   - Severity classification (CRITICAL / HIGH / MODERATE / LOW / NONE)
   - Interaction type (pharmacokinetic, pharmacodynamic, etc.)
   - Clinical mechanism
   - Clinical effect on the patient
   - Management recommendation
   - Plain-language patient summary
   - Alternative drug suggestions for both drugs
4. Filter out NONE interactions; store results in `PHARMACY.DRUG_INTERACTIONS`
5. Create `PATIENT_DRUG_INTERACTION_ALERTS` view that joins patient prescriptions
   against the interaction reference

**Output:** `PHARMACY.DRUG_INTERACTIONS` table, `PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS` view

**Data Quality Notes:**
- AI-generated interaction data is grounded in clinical pharmacology knowledge
- For production use, replace with DrugBank Marketplace data (`GZTYZJ6Q7W0`)
- Severity ratings align with standard clinical interaction scales

### 2. Semantic Views (`03_semantic_views.sql`)

Three semantic views created for Cortex Analyst/Agent grounding:

| Semantic View | Source | Purpose |
|---|---|---|
| `SV_PATIENT_MEDICATIONS` | Patients + Prescriptions + Medications + Providers | Medication profile queries |
| `SV_DRUG_INTERACTION_ALERTS` | Patient interaction alerts view | Interaction alert queries |
| `SV_PATIENT_ENCOUNTERS` | Encounters + Diagnoses + Patients + Providers | Clinical history queries |

Each view includes column-level comments describing semantics for Cortex Analyst.

### 3. Cortex Search Services (`04_cortex_search.sql`)

Two search services for semantic retrieval:

| Service | Corpus | Use Case |
|---|---|---|
| `DRUG_INTERACTION_SEARCH` | Drug interaction descriptions, mechanisms, alternatives | "What happens if I take X with Y?" |
| `PHARMACIST_NOTES_SEARCH` | Prescription pharmacist notes | "What did the pharmacist say about my medication?" |

Both services refresh every hour and support attribute filtering.

### 4. Cortex Agent (`05_cortex_agent.sql`)

The agent is wired to:
- 3 semantic views (Cortex Analyst for structured queries)
- 2 Cortex Search services (for semantic retrieval)

Agent instructions guide clinical pharmacist behavior, severity-aware responses,
and patient vs. provider tone adaptation.

### 5. Email Alert Pipeline (`07_email_pipeline.sql`)

**Trigger:** Snowflake Task running every 6 hours

**Process:**
1. Query `PATIENT_DRUG_INTERACTION_ALERTS` for CRITICAL and HIGH severity
2. Check `ALERT_EMAIL_LOG` to skip already-emailed alerts
3. Use `AI_COMPLETE` to generate professional medical alert email
4. Log email content, subject, provider, and timestamp
5. Alert both prescribing providers if they differ

**Output:** `PHARMACY.ALERT_EMAIL_LOG` table

### 6. Security Model (`06_security.sql`)

**Restricted Caller's Rights pattern:**

```
End User (DRUG_INTERACTION_USER_ROLE)
    │
    │  CALL procedure (has USAGE grant)
    │
    ▼
RCR Stored Procedure (EXECUTE AS OWNER)
    │
    │  Runs with DRUG_INTERACTION_APP_ROLE privileges
    │
    ▼
Underlying Tables (only APP_ROLE has SELECT)
```

Three RCR procedures:
- `GET_PATIENT_ALERTS(patient_id)` — Patient interaction alerts
- `GET_PROVIDER_PANEL(provider_id)` — Provider's full patient panel
- `GET_TRANSLATED_ALERT(patient_id, interaction_id)` — AI_TRANSLATE'd alert

## Marketplace Data (Optional Enhancement)

When available, replace AI-generated interactions with curated data:

| Listing | Global Name | Key Data |
|---|---|---|
| DrugBank Biomedical Knowledge | `GZTYZJ6Q7W0` | 500K+ drugs, drug-drug interactions with severity |
| FDA FAERS Adverse Events | `GZ2FWZ5FDDY` | 5.6M+ adverse event reports, drug-reaction links |
