/*
 * 04_cortex_search.sql
 * Cortex Search service over drug interactions and pharmacist notes.
 * Enables semantic search for the chat interface and agent tools.
 */

USE DATABASE HEALTHCARE_DW;
USE SCHEMA PHARMACY;

-- Materialized search corpus: drug interactions with full context
CREATE OR REPLACE TABLE HEALTHCARE_DW.PHARMACY.SEARCH_DRUG_INTERACTIONS AS
SELECT
    di.INTERACTION_ID,
    di.DRUG_A_NAME,
    di.DRUG_B_NAME,
    di.SEVERITY,
    di.INTERACTION_TYPE,
    di.MECHANISM,
    di.CLINICAL_EFFECT,
    di.MANAGEMENT,
    di.PATIENT_SUMMARY,
    di.ALTERNATIVE_FOR_A,
    di.ALTERNATIVE_FOR_B,
    -- Rich text column for search
    CONCAT(
        'Drug interaction between ', di.DRUG_A_NAME, ' and ', di.DRUG_B_NAME, '. ',
        'Severity: ', di.SEVERITY, '. ',
        'Type: ', COALESCE(di.INTERACTION_TYPE, 'Unknown'), '. ',
        'Mechanism: ', COALESCE(di.MECHANISM, 'Unknown'), '. ',
        'Clinical effect: ', COALESCE(di.CLINICAL_EFFECT, 'Unknown'), '. ',
        'Management: ', COALESCE(di.MANAGEMENT, 'Unknown'), '. ',
        'Patient summary: ', COALESCE(di.PATIENT_SUMMARY, ''), '. ',
        'Alternative for ', di.DRUG_A_NAME, ': ', COALESCE(di.ALTERNATIVE_FOR_A, 'N/A'), '. ',
        'Alternative for ', di.DRUG_B_NAME, ': ', COALESCE(di.ALTERNATIVE_FOR_B, 'N/A'), '.'
    ) AS SEARCH_TEXT
FROM HEALTHCARE_DW.PHARMACY.DRUG_INTERACTIONS di;

-- Materialized search corpus: pharmacist notes from prescriptions
CREATE OR REPLACE TABLE HEALTHCARE_DW.PHARMACY.SEARCH_PHARMACIST_NOTES AS
SELECT
    rx.PRESCRIPTION_ID,
    rx.PATIENT_ID,
    rx.MEDICATION_NAME,
    m.DRUG_CLASS,
    m.GENERIC_NAME,
    rx.DOSAGE,
    rx.FREQUENCY,
    rx.PHARMACIST_NOTES,
    CONCAT(
        'Prescription for ', rx.MEDICATION_NAME, ' (', m.GENERIC_NAME, ', ', m.DRUG_CLASS, '). ',
        'Dosage: ', rx.DOSAGE, ', Frequency: ', rx.FREQUENCY, '. ',
        'Pharmacist notes: ', COALESCE(rx.PHARMACIST_NOTES, 'None'), '.'
    ) AS SEARCH_TEXT
FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx
JOIN HEALTHCARE_DW.PHARMACY.MEDICATIONS m ON rx.MEDICATION_ID = m.MEDICATION_ID;

-- Create Cortex Search service for drug interactions
CREATE OR REPLACE CORTEX SEARCH SERVICE HEALTHCARE_DW.PHARMACY.DRUG_INTERACTION_SEARCH
  ON SEARCH_TEXT
  ATTRIBUTES SEVERITY, DRUG_A_NAME, DRUG_B_NAME
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
  AS (
    SELECT * FROM HEALTHCARE_DW.PHARMACY.SEARCH_DRUG_INTERACTIONS
  );

-- Create Cortex Search service for pharmacist notes
CREATE OR REPLACE CORTEX SEARCH SERVICE HEALTHCARE_DW.PHARMACY.PHARMACIST_NOTES_SEARCH
  ON SEARCH_TEXT
  ATTRIBUTES MEDICATION_NAME, DRUG_CLASS
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
  AS (
    SELECT * FROM HEALTHCARE_DW.PHARMACY.SEARCH_PHARMACIST_NOTES
  );
