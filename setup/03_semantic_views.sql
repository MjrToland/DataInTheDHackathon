/*
 * 03_semantic_views.sql
 * Semantic views for Cortex Analyst / Agent grounding.
 * Uses real CREATE SEMANTIC VIEW DDL with TABLES/RELATIONSHIPS/DIMENSIONS/METRICS.
 */

USE DATABASE HEALTHCARE_DW;
USE SCHEMA DDI_APP;

-- Semantic view: Patient medication profiles
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.DDI_APP.SV_PATIENT_MEDICATIONS
  TABLES (
    patients AS HEALTHCARE_DW.CORE.PATIENTS PRIMARY KEY (PATIENT_ID)
      COMMENT = 'Patient demographics',
    prescriptions AS HEALTHCARE_DW.PHARMACY.PRESCRIPTIONS PRIMARY KEY (PRESCRIPTION_ID)
      COMMENT = 'Prescription records. STATUS: FILLED=current, PENDING, CANCELLED',
    medications AS HEALTHCARE_DW.PHARMACY.MEDICATIONS PRIMARY KEY (MEDICATION_ID)
      COMMENT = 'Drug formulary (20 medications)',
    providers AS HEALTHCARE_DW.CORE.PROVIDERS PRIMARY KEY (PROVIDER_ID)
      COMMENT = 'Healthcare providers',
    prefs AS HEALTHCARE_DW.DDI_APP.PATIENT_PREFERENCES PRIMARY KEY (PATIENT_ID)
      COMMENT = 'Patient language preferences'
  )
  RELATIONSHIPS (
    rx_to_patient AS prescriptions (PATIENT_ID) REFERENCES patients,
    rx_to_med AS prescriptions (MEDICATION_ID) REFERENCES medications,
    rx_to_provider AS prescriptions (PROVIDER_ID) REFERENCES providers,
    prefs_to_patient AS prefs (PATIENT_ID) REFERENCES patients
  )
  DIMENSIONS (
    patients.patient_name AS patients.FIRST_NAME || ' ' || patients.LAST_NAME COMMENT = 'Full patient name',
    patients.gender AS patients.GENDER COMMENT = 'Patient gender',
    patients.state AS patients.STATE_CODE COMMENT = 'US state code',
    patients.insurance AS patients.PRIMARY_INSURANCE COMMENT = 'Insurance provider',
    patients.has_chronic_condition AS patients.HAS_CHRONIC_CONDITION COMMENT = 'Chronic condition flag',
    prescriptions.status AS prescriptions.STATUS COMMENT = 'Rx status: FILLED/PENDING/CANCELLED',
    prescriptions.medication_name AS prescriptions.MEDICATION_NAME COMMENT = 'Prescribed medication name',
    prescriptions.dosage AS prescriptions.DOSAGE COMMENT = 'Dosage amount',
    prescriptions.frequency AS prescriptions.FREQUENCY COMMENT = 'Dosing frequency',
    prescriptions.prescribed_date AS prescriptions.PRESCRIBED_DATE COMMENT = 'Date prescribed',
    medications.drug_class AS medications.DRUG_CLASS COMMENT = 'Pharmacological class',
    medications.generic_name AS medications.GENERIC_NAME COMMENT = 'Generic drug name',
    medications.brand_name AS medications.BRAND_NAME COMMENT = 'Brand drug name',
    medications.route AS medications.ROUTE COMMENT = 'Route of administration',
    providers.provider_name AS providers.FIRST_NAME || ' ' || providers.LAST_NAME COMMENT = 'Prescriber name',
    providers.specialty AS providers.SPECIALTY COMMENT = 'Medical specialty',
    prefs.preferred_language AS prefs.PREFERRED_LANGUAGE COMMENT = 'Patient language code'
  )
  METRICS (
    prescriptions.total_prescriptions AS COUNT(prescriptions.PRESCRIPTION_ID) COMMENT = 'Total prescriptions',
    prescriptions.avg_cost AS AVG(prescriptions.COST) COMMENT = 'Average Rx cost',
    prescriptions.total_cost AS SUM(prescriptions.COST) COMMENT = 'Total Rx cost',
    patients.patient_count AS COUNT(DISTINCT patients.PATIENT_ID) COMMENT = 'Distinct patients',
    prescriptions.distinct_medications AS COUNT(DISTINCT prescriptions.MEDICATION_ID) COMMENT = 'Distinct meds'
  )
  COMMENT = 'Patient medication profiles. Filter STATUS=FILLED for current medications.';

-- Semantic view: Drug interaction alerts
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.DDI_APP.SV_DRUG_INTERACTION_ALERTS
  TABLES (
    alerts AS HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS PRIMARY KEY (PATIENT_ID, INTERACTION_ID)
      COMMENT = 'Active drug interaction alerts. AI-generated, not clinically validated.'
  )
  DIMENSIONS (
    alerts.patient_name AS alerts.FIRST_NAME || ' ' || alerts.LAST_NAME COMMENT = 'Patient name',
    alerts.drug_a AS alerts.DRUG_A_NAME COMMENT = 'First drug in pair',
    alerts.drug_b AS alerts.DRUG_B_NAME COMMENT = 'Second drug in pair',
    alerts.severity AS alerts.SEVERITY COMMENT = 'CRITICAL/HIGH/MODERATE/LOW',
    alerts.interaction_type AS alerts.INTERACTION_TYPE COMMENT = 'Interaction type',
    alerts.mechanism AS alerts.MECHANISM COMMENT = 'Interaction mechanism',
    alerts.clinical_effect AS alerts.CLINICAL_EFFECT COMMENT = 'Clinical effect',
    alerts.management AS alerts.MANAGEMENT COMMENT = 'Management recommendation',
    alerts.patient_summary AS alerts.PATIENT_SUMMARY COMMENT = 'Plain-language summary',
    alerts.alternative_for_a AS alerts.ALTERNATIVE_FOR_A COMMENT = 'Alternative for drug A',
    alerts.alternative_for_b AS alerts.ALTERNATIVE_FOR_B COMMENT = 'Alternative for drug B',
    alerts.prescriber_a_name AS alerts.PRESCRIBER_A_NAME COMMENT = 'Drug A prescriber',
    alerts.prescriber_b_name AS alerts.PRESCRIBER_B_NAME COMMENT = 'Drug B prescriber',
    alerts.preferred_language AS alerts.PREFERRED_LANGUAGE COMMENT = 'Patient language',
    alerts.has_chronic_condition AS alerts.HAS_CHRONIC_CONDITION COMMENT = 'Chronic condition flag'
  )
  METRICS (
    alerts.total_alerts AS COUNT(*) COMMENT = 'Total alerts',
    alerts.patients_affected AS COUNT(DISTINCT alerts.PATIENT_ID) COMMENT = 'Distinct patients',
    alerts.critical_alerts AS COUNT_IF(alerts.SEVERITY = 'CRITICAL') COMMENT = 'Critical count',
    alerts.high_alerts AS COUNT_IF(alerts.SEVERITY = 'HIGH') COMMENT = 'High count'
  )
  COMMENT = 'Drug interaction alerts. AI-generated, not clinically validated.';

-- Semantic view: Clinical encounters
CREATE OR REPLACE SEMANTIC VIEW HEALTHCARE_DW.DDI_APP.SV_PATIENT_ENCOUNTERS
  TABLES (
    encounters AS HEALTHCARE_DW.CLINICAL.ENCOUNTERS PRIMARY KEY (ENCOUNTER_ID)
      COMMENT = 'Clinical encounters',
    patients AS HEALTHCARE_DW.CORE.PATIENTS PRIMARY KEY (PATIENT_ID)
      COMMENT = 'Patient demographics',
    providers AS HEALTHCARE_DW.CORE.PROVIDERS PRIMARY KEY (PROVIDER_ID)
      COMMENT = 'Healthcare providers',
    diagnoses AS HEALTHCARE_DW.CLINICAL.DIAGNOSES PRIMARY KEY (ENCOUNTER_ID, ICD10_CODE)
      COMMENT = 'Diagnoses with ICD-10 codes'
  )
  RELATIONSHIPS (
    encounter_to_patient AS encounters (PATIENT_ID) REFERENCES patients,
    encounter_to_provider AS encounters (PROVIDER_ID) REFERENCES providers,
    diagnosis_to_encounter AS diagnoses (ENCOUNTER_ID) REFERENCES encounters
  )
  DIMENSIONS (
    patients.patient_name AS patients.FIRST_NAME || ' ' || patients.LAST_NAME COMMENT = 'Patient name',
    encounters.encounter_date AS encounters.ENCOUNTER_DATE COMMENT = 'Encounter date',
    encounters.encounter_type AS encounters.ENCOUNTER_TYPE COMMENT = 'Visit type',
    encounters.chief_complaint AS encounters.CHIEF_COMPLAINT COMMENT = 'Chief complaint',
    encounters.encounter_status AS encounters.STATUS COMMENT = 'Encounter status',
    providers.provider_name AS providers.FIRST_NAME || ' ' || providers.LAST_NAME COMMENT = 'Provider name',
    providers.specialty AS providers.SPECIALTY COMMENT = 'Provider specialty',
    diagnoses.icd10_code AS diagnoses.ICD10_CODE COMMENT = 'ICD-10 code',
    diagnoses.diagnosis_description AS diagnoses.DIAGNOSIS_DESCRIPTION COMMENT = 'Diagnosis description',
    diagnoses.diagnosis_category AS diagnoses.CATEGORY COMMENT = 'Diagnosis category',
    diagnoses.is_chronic AS diagnoses.IS_CHRONIC COMMENT = 'Chronic condition flag'
  )
  METRICS (
    encounters.total_encounters AS COUNT(encounters.ENCOUNTER_ID) COMMENT = 'Total encounters',
    encounters.avg_length_of_stay AS AVG(encounters.LENGTH_OF_STAY_DAYS) COMMENT = 'Avg LOS in days',
    patients.patient_count AS COUNT(DISTINCT patients.PATIENT_ID) COMMENT = 'Distinct patients'
  )
  COMMENT = 'Clinical encounters with diagnoses.';
