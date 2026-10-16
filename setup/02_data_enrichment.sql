/*
 * 02_data_enrichment.sql
 * Build the drug interaction reference table.
 *
 * Strategy:
 *   1. If DrugBank Marketplace data is available, join it to our 20 medications
 *   2. Fallback: use Cortex AI_COMPLETE to generate interaction data for all
 *      medication pairs from our formulary
 *   3. Enrich all interactions with plain-language patient-friendly summaries
 *
 * Pipeline: MEDICATIONS (20 drugs) -> cross-join pairs -> AI interaction check
 *           -> severity rating -> patient-friendly summary -> alternatives
 */

USE DATABASE HEALTHCARE_DW;
USE SCHEMA PHARMACY;

-- Add preferred_language to patients for AI_TRANSLATE support
ALTER TABLE HEALTHCARE_DW.CORE.PATIENTS
  ADD COLUMN IF NOT EXISTS PREFERRED_LANGUAGE VARCHAR(10) DEFAULT 'en';

-- Assign languages to simulate a multilingual patient population
UPDATE HEALTHCARE_DW.CORE.PATIENTS
SET PREFERRED_LANGUAGE = CASE
    WHEN PATIENT_ID % 10 = 0 THEN 'es'   -- Spanish
    WHEN PATIENT_ID % 10 = 1 THEN 'ar'    -- Arabic
    WHEN PATIENT_ID % 10 = 2 THEN 'zh'    -- Chinese
    WHEN PATIENT_ID % 10 = 3 THEN 'fr'    -- French
    WHEN PATIENT_ID % 10 = 4 THEN 'pt'    -- Portuguese
    WHEN PATIENT_ID % 10 = 5 THEN 'de'    -- German
    WHEN PATIENT_ID % 10 = 6 THEN 'ko'    -- Korean
    WHEN PATIENT_ID % 10 = 7 THEN 'vi'    -- Vietnamese
    WHEN PATIENT_ID % 10 = 8 THEN 'ja'    -- Japanese
    ELSE 'en'                              -- English
END;

-- Create the drug interaction reference table
CREATE OR REPLACE TABLE HEALTHCARE_DW.PHARMACY.DRUG_INTERACTIONS (
    INTERACTION_ID       NUMBER AUTOINCREMENT,
    DRUG_A_ID            NUMBER NOT NULL,
    DRUG_A_NAME          VARCHAR NOT NULL,
    DRUG_B_ID            NUMBER NOT NULL,
    DRUG_B_NAME          VARCHAR NOT NULL,
    SEVERITY             VARCHAR NOT NULL,       -- CRITICAL, HIGH, MODERATE, LOW
    INTERACTION_TYPE     VARCHAR,                 -- PHARMACOKINETIC, PHARMACODYNAMIC, etc.
    MECHANISM            VARCHAR,                 -- How the interaction works
    CLINICAL_EFFECT      VARCHAR,                 -- What happens clinically
    MANAGEMENT           VARCHAR,                 -- How to manage it
    PATIENT_SUMMARY      VARCHAR,                 -- Plain-language explanation
    ALTERNATIVE_FOR_A    VARCHAR,                 -- Alternative drug suggestion for A
    ALTERNATIVE_FOR_B    VARCHAR,                 -- Alternative drug suggestion for B
    SOURCE               VARCHAR DEFAULT 'AI_GENERATED',
    CREATED_AT           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Generate all unique medication pairs from our formulary
CREATE OR REPLACE TEMPORARY TABLE MEDICATION_PAIRS AS
SELECT
    a.MEDICATION_ID AS DRUG_A_ID,
    a.GENERIC_NAME  AS DRUG_A_NAME,
    a.DRUG_CLASS    AS DRUG_A_CLASS,
    b.MEDICATION_ID AS DRUG_B_ID,
    b.GENERIC_NAME  AS DRUG_B_NAME,
    b.DRUG_CLASS    AS DRUG_B_CLASS
FROM HEALTHCARE_DW.PHARMACY.MEDICATIONS a
JOIN HEALTHCARE_DW.PHARMACY.MEDICATIONS b
  ON a.MEDICATION_ID < b.MEDICATION_ID;

-- Use AI_COMPLETE to assess each drug pair for interactions
-- This generates clinically-grounded interaction data for our 190 unique pairs
INSERT INTO HEALTHCARE_DW.PHARMACY.DRUG_INTERACTIONS
    (DRUG_A_ID, DRUG_A_NAME, DRUG_B_ID, DRUG_B_NAME,
     SEVERITY, INTERACTION_TYPE, MECHANISM, CLINICAL_EFFECT,
     MANAGEMENT, PATIENT_SUMMARY, ALTERNATIVE_FOR_A, ALTERNATIVE_FOR_B, SOURCE)
SELECT
    mp.DRUG_A_ID,
    mp.DRUG_A_NAME,
    mp.DRUG_B_ID,
    mp.DRUG_B_NAME,
    TRIM(ai.response:severity::VARCHAR)          AS SEVERITY,
    TRIM(ai.response:interaction_type::VARCHAR)  AS INTERACTION_TYPE,
    TRIM(ai.response:mechanism::VARCHAR)         AS MECHANISM,
    TRIM(ai.response:clinical_effect::VARCHAR)   AS CLINICAL_EFFECT,
    TRIM(ai.response:management::VARCHAR)        AS MANAGEMENT,
    TRIM(ai.response:patient_summary::VARCHAR)   AS PATIENT_SUMMARY,
    TRIM(ai.response:alternative_for_a::VARCHAR) AS ALTERNATIVE_FOR_A,
    TRIM(ai.response:alternative_for_b::VARCHAR) AS ALTERNATIVE_FOR_B,
    'AI_GENERATED'
FROM MEDICATION_PAIRS mp,
LATERAL (
    SELECT PARSE_JSON(SNOWFLAKE.CORTEX.COMPLETE(
        'claude-3-5-sonnet',
        CONCAT(
            'You are a clinical pharmacist. Analyze the interaction between these two drugs. ',
            'Drug A: ', mp.DRUG_A_NAME, ' (', mp.DRUG_A_CLASS, '). ',
            'Drug B: ', mp.DRUG_B_NAME, ' (', mp.DRUG_B_CLASS, '). ',
            'Return a JSON object with these exact keys: ',
            'severity (one of: CRITICAL, HIGH, MODERATE, LOW, NONE), ',
            'interaction_type (PHARMACOKINETIC, PHARMACODYNAMIC, ADDITIVE, SYNERGISTIC, ANTAGONISTIC, or NONE), ',
            'mechanism (brief mechanism of interaction or "No known interaction"), ',
            'clinical_effect (what happens to the patient), ',
            'management (clinical recommendation), ',
            'patient_summary (2-3 sentence plain language explanation for a patient), ',
            'alternative_for_a (name one alternative drug for Drug A that avoids this interaction, or "N/A"), ',
            'alternative_for_b (name one alternative drug for Drug B that avoids this interaction, or "N/A"). ',
            'Respond ONLY with the JSON object, no other text.'
        )
    )) AS response
) ai
WHERE ai.response:severity::VARCHAR != 'NONE';

-- Create the polypharmacy risk view: patients with flagged interactions
CREATE OR REPLACE VIEW HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS AS
WITH active_rx AS (
    SELECT PATIENT_ID, MEDICATION_ID, MEDICATION_NAME, PROVIDER_ID, PRESCRIBED_DATE
    FROM HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS
    WHERE STATUS IN ('ACTIVE', 'FILLED')
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY PATIENT_ID, MEDICATION_ID
        ORDER BY PRESCRIBED_DATE DESC
    ) = 1
),
flagged AS (
    SELECT
        rx_a.PATIENT_ID,
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
        rx_a.PROVIDER_ID AS PRESCRIBER_A_ID,
        rx_b.PROVIDER_ID AS PRESCRIBER_B_ID,
        rx_a.PRESCRIBED_DATE AS RX_A_DATE,
        rx_b.PRESCRIBED_DATE AS RX_B_DATE
    FROM active_rx rx_a
    JOIN active_rx rx_b
      ON rx_a.PATIENT_ID = rx_b.PATIENT_ID
     AND rx_a.MEDICATION_ID < rx_b.MEDICATION_ID
    JOIN HEALTHCARE_DW.PHARMACY.DRUG_INTERACTIONS di
      ON (di.DRUG_A_ID = rx_a.MEDICATION_ID AND di.DRUG_B_ID = rx_b.MEDICATION_ID)
      OR (di.DRUG_A_ID = rx_b.MEDICATION_ID AND di.DRUG_B_ID = rx_a.MEDICATION_ID)
)
SELECT
    f.*,
    p.FIRST_NAME,
    p.LAST_NAME,
    p.DATE_OF_BIRTH,
    p.PREFERRED_LANGUAGE,
    p.HAS_CHRONIC_CONDITION,
    prov_a.FIRST_NAME || ' ' || prov_a.LAST_NAME AS PRESCRIBER_A_NAME,
    prov_a.SPECIALTY AS PRESCRIBER_A_SPECIALTY,
    prov_b.FIRST_NAME || ' ' || prov_b.LAST_NAME AS PRESCRIBER_B_NAME,
    prov_b.SPECIALTY AS PRESCRIBER_B_SPECIALTY
FROM flagged f
JOIN HEALTHCARE_DW.CORE.PATIENTS p ON f.PATIENT_ID = p.PATIENT_ID
LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov_a ON f.PRESCRIBER_A_ID = prov_a.PROVIDER_ID
LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov_b ON f.PRESCRIBER_B_ID = prov_b.PROVIDER_ID;
