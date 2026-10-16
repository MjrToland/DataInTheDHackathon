/*
 * 03_semantic_views.sql
 * Semantic views over HEALTHCARE_DW for Cortex Analyst / Agent grounding.
 * These enable natural-language queries against the healthcare data.
 */

USE DATABASE HEALTHCARE_DW;

-- Semantic view: Patient medication profile
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.PHARMACY.SV_PATIENT_MEDICATIONS
  AS SELECT * FROM (
    SELECT
        p.PATIENT_ID,
        p.FIRST_NAME,
        p.LAST_NAME,
        p.DATE_OF_BIRTH,
        p.GENDER,
        p.STATE_CODE,
        p.PRIMARY_INSURANCE,
        p.HAS_CHRONIC_CONDITION,
        p.PREFERRED_LANGUAGE,
        rx.PRESCRIPTION_ID,
        rx.RX_NUMBER,
        rx.MEDICATION_NAME,
        rx.DOSAGE,
        rx.FREQUENCY,
        rx.PRESCRIBED_DATE,
        rx.DAYS_SUPPLY,
        rx.REFILLS_REMAINING,
        rx.COST AS PRESCRIPTION_COST,
        rx.STATUS AS PRESCRIPTION_STATUS,
        m.DRUG_CLASS,
        m.GENERIC_NAME,
        m.BRAND_NAME,
        m.ROUTE,
        m.TREATS_ICD10,
        prov.FIRST_NAME || ' ' || prov.LAST_NAME AS PRESCRIBER_NAME,
        prov.SPECIALTY AS PRESCRIBER_SPECIALTY
    FROM HEALTHCARE_DW.CORE.PATIENTS p
    JOIN HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS rx ON p.PATIENT_ID = rx.PATIENT_ID
    JOIN HEALTHCARE_DW.PHARMACY.MEDICATIONS m ON rx.MEDICATION_ID = m.MEDICATION_ID
    LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov ON rx.PROVIDER_ID = prov.PROVIDER_ID
  )
  COMMENT = 'Patient medication profiles with prescriptions, drug details, and prescriber info.
             Use to answer questions about what medications patients are taking, prescription costs,
             drug classes, refill status, and prescriber details.'
  COLUMNS (
    PATIENT_ID COMMENT 'Unique patient identifier',
    FIRST_NAME COMMENT 'Patient first name',
    LAST_NAME COMMENT 'Patient last name',
    DATE_OF_BIRTH COMMENT 'Patient date of birth',
    GENDER COMMENT 'Patient gender',
    STATE_CODE COMMENT 'Patient state of residence (2-letter code)',
    PRIMARY_INSURANCE COMMENT 'Patient primary insurance provider',
    HAS_CHRONIC_CONDITION COMMENT 'Whether patient has a chronic condition (TRUE/FALSE)',
    PREFERRED_LANGUAGE COMMENT 'Patient preferred language code (en, es, ar, zh, fr, pt, de, ko, vi, ja)',
    PRESCRIPTION_ID COMMENT 'Unique prescription identifier',
    RX_NUMBER COMMENT 'Prescription number (format: RX-XXXXXXXXXX)',
    MEDICATION_NAME COMMENT 'Name of the prescribed medication',
    DOSAGE COMMENT 'Medication dosage (e.g., 20mg, 100mg)',
    FREQUENCY COMMENT 'How often the medication is taken (e.g., Once daily, Twice daily, As needed)',
    PRESCRIBED_DATE COMMENT 'Date the prescription was written',
    DAYS_SUPPLY COMMENT 'Number of days the prescription covers',
    REFILLS_REMAINING COMMENT 'Number of refills remaining',
    PRESCRIPTION_COST COMMENT 'Cost of the prescription in dollars',
    PRESCRIPTION_STATUS COMMENT 'Status of the prescription (ACTIVE, FILLED, EXPIRED, CANCELLED)',
    DRUG_CLASS COMMENT 'Pharmacological drug class (e.g., SSRI, Statin, Beta Blocker)',
    GENERIC_NAME COMMENT 'Generic drug name',
    BRAND_NAME COMMENT 'Brand drug name',
    ROUTE COMMENT 'Route of administration (ORAL, INHALED, TOPICAL)',
    TREATS_ICD10 COMMENT 'ICD-10 code for the condition the drug treats',
    PRESCRIBER_NAME COMMENT 'Name of the prescribing provider',
    PRESCRIBER_SPECIALTY COMMENT 'Medical specialty of the prescriber'
  );

-- Semantic view: Drug interaction alerts
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.PHARMACY.SV_DRUG_INTERACTION_ALERTS
  AS SELECT * FROM HEALTHCARE_DW.PHARMACY.PATIENT_DRUG_INTERACTION_ALERTS
  COMMENT = 'Active drug interaction alerts for patients currently taking conflicting medications.
             Use to answer questions about dangerous drug combinations, interaction severity,
             alternative medications, and which providers to notify.'
  COLUMNS (
    PATIENT_ID COMMENT 'Patient with the flagged interaction',
    INTERACTION_ID COMMENT 'Unique interaction pair identifier',
    DRUG_A_NAME COMMENT 'First drug in the interacting pair',
    DRUG_B_NAME COMMENT 'Second drug in the interacting pair',
    SEVERITY COMMENT 'Interaction severity: CRITICAL (life-threatening), HIGH (serious harm), MODERATE (monitor closely), LOW (minor)',
    INTERACTION_TYPE COMMENT 'Type: PHARMACOKINETIC, PHARMACODYNAMIC, ADDITIVE, SYNERGISTIC, ANTAGONISTIC',
    MECHANISM COMMENT 'How the two drugs interact mechanistically',
    CLINICAL_EFFECT COMMENT 'What effect the interaction has on the patient',
    MANAGEMENT COMMENT 'Clinical recommendation for managing the interaction',
    PATIENT_SUMMARY COMMENT 'Plain-language explanation of the interaction for patients',
    ALTERNATIVE_FOR_A COMMENT 'Suggested alternative medication to replace Drug A',
    ALTERNATIVE_FOR_B COMMENT 'Suggested alternative medication to replace Drug B',
    PRESCRIBER_A_ID COMMENT 'Provider who prescribed Drug A',
    PRESCRIBER_B_ID COMMENT 'Provider who prescribed Drug B',
    RX_A_DATE COMMENT 'Date Drug A was prescribed',
    RX_B_DATE COMMENT 'Date Drug B was prescribed',
    FIRST_NAME COMMENT 'Patient first name',
    LAST_NAME COMMENT 'Patient last name',
    DATE_OF_BIRTH COMMENT 'Patient date of birth',
    PREFERRED_LANGUAGE COMMENT 'Patient preferred language',
    HAS_CHRONIC_CONDITION COMMENT 'Whether patient has a chronic condition',
    PRESCRIBER_A_NAME COMMENT 'Name of the provider who prescribed Drug A',
    PRESCRIBER_A_SPECIALTY COMMENT 'Specialty of the provider who prescribed Drug A',
    PRESCRIBER_B_NAME COMMENT 'Name of the provider who prescribed Drug B',
    PRESCRIBER_B_SPECIALTY COMMENT 'Specialty of the provider who prescribed Drug B'
  );

-- Semantic view: Clinical encounters and diagnoses
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.CLINICAL.SV_PATIENT_ENCOUNTERS
  AS SELECT * FROM (
    SELECT
        e.ENCOUNTER_ID,
        e.PATIENT_ID,
        p.FIRST_NAME,
        p.LAST_NAME,
        e.ENCOUNTER_DATE,
        e.ENCOUNTER_TYPE,
        e.CHIEF_COMPLAINT,
        e.LENGTH_OF_STAY_DAYS,
        e.STATUS AS ENCOUNTER_STATUS,
        prov.FIRST_NAME || ' ' || prov.LAST_NAME AS PROVIDER_NAME,
        prov.SPECIALTY AS PROVIDER_SPECIALTY,
        dx.ICD10_CODE,
        dx.DIAGNOSIS_DESCRIPTION,
        dx.CATEGORY AS DIAGNOSIS_CATEGORY,
        dx.IS_CHRONIC,
        dx.DIAGNOSIS_RANK
    FROM HEALTHCARE_DW.CLINICAL.ENCOUNTERS e
    JOIN HEALTHCARE_DW.CORE.PATIENTS p ON e.PATIENT_ID = p.PATIENT_ID
    LEFT JOIN HEALTHCARE_DW.CORE.PROVIDERS prov ON e.PROVIDER_ID = prov.PROVIDER_ID
    LEFT JOIN HEALTHCARE_DW.CLINICAL.DIAGNOSES dx ON e.ENCOUNTER_ID = dx.ENCOUNTER_ID
  )
  COMMENT = 'Patient clinical encounters with diagnoses. Use to answer questions about
             patient visits, diagnoses, conditions, encounter types, and provider assignments.'
  COLUMNS (
    ENCOUNTER_ID COMMENT 'Unique encounter identifier',
    PATIENT_ID COMMENT 'Patient involved in the encounter',
    FIRST_NAME COMMENT 'Patient first name',
    LAST_NAME COMMENT 'Patient last name',
    ENCOUNTER_DATE COMMENT 'Date of the encounter',
    ENCOUNTER_TYPE COMMENT 'Type: OUTPATIENT, OFFICE_VISIT, TELEHEALTH, INPATIENT, URGENT_CARE, EMERGENCY',
    CHIEF_COMPLAINT COMMENT 'Primary reason for the visit',
    LENGTH_OF_STAY_DAYS COMMENT 'Length of stay in days (for inpatient)',
    ENCOUNTER_STATUS COMMENT 'Encounter status',
    PROVIDER_NAME COMMENT 'Name of the attending provider',
    PROVIDER_SPECIALTY COMMENT 'Specialty of the attending provider',
    ICD10_CODE COMMENT 'ICD-10 diagnosis code',
    DIAGNOSIS_DESCRIPTION COMMENT 'Description of the diagnosis',
    DIAGNOSIS_CATEGORY COMMENT 'Category: Musculoskeletal, Cardiovascular, Endocrine, Respiratory, Neurological, etc.',
    IS_CHRONIC COMMENT 'Whether the diagnosis is a chronic condition',
    DIAGNOSIS_RANK COMMENT 'Rank of the diagnosis (PRIMARY, SECONDARY, etc.)'
  );
