/*
 * 05_cortex_agent.sql
 * Cortex Agent for the drug interaction chat interface.
 *
 * NOTE: DATA_AGENT_RUN has a known issue with warehouse resolution.
 * The chat page falls back to Cortex Search + AI_COMPLETE as a workaround.
 */

USE DATABASE HEALTHCARE_DW;
USE SCHEMA DDI_APP;

CREATE OR REPLACE AGENT HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_AGENT
  COMMENT = 'AI agent for drug interaction detection, medication questions, and patient safety alerts'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto

  orchestration:
    tool_not_accessible: accept
    budget:
      seconds: 60
      tokens: 32000

  instructions:
    response: |
      You are a clinical pharmacist AI assistant. Help healthcare providers understand drug interactions,
      medication safety, and treatment alternatives. Always cite severity levels. For CRITICAL/HIGH,
      emphasize urgency. All interaction data is AI-generated and not clinically validated.
      Prescription status FILLED = current/active.

    orchestration: |
      For patient/medication/count questions use Analyst tools. For drug interaction mechanisms/effects use Search tools.

    sample_questions:
      - question: "What are the interactions for patient 53115?"
      - question: "How many patients have critical interactions?"

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "PatientMedications"
        description: "Query patient medication profiles, prescriptions, drug classes, costs, and prescriber details"
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "InteractionAlerts"
        description: "Query drug interaction alerts including severity, affected patients, drug pairs, and management"
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "ClinicalEncounters"
        description: "Query clinical encounters, diagnoses, conditions, and provider assignments"
    - tool_spec:
        type: "cortex_search"
        name: "DrugInteractionSearch"
        description: "Search drug interaction knowledge base for mechanisms, effects, and alternatives"
    - tool_spec:
        type: "cortex_search"
        name: "PharmacistNotesSearch"
        description: "Search pharmacist notes from prescriptions"

  tool_resources:
    PatientMedications:
      semantic_view: "HEALTHCARE_DW.DDI_APP.SV_PATIENT_MEDICATIONS"
    InteractionAlerts:
      semantic_view: "HEALTHCARE_DW.DDI_APP.SV_DRUG_INTERACTION_ALERTS"
    ClinicalEncounters:
      semantic_view: "HEALTHCARE_DW.DDI_APP.SV_PATIENT_ENCOUNTERS"
    DrugInteractionSearch:
      search_service: "HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_SEARCH"
      max_results: "5"
    PharmacistNotesSearch:
      search_service: "HEALTHCARE_DW.DDI_APP.PHARMACIST_NOTES_SEARCH"
      max_results: "5"
  $$;
