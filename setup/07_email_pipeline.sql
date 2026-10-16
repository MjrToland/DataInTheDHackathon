/*
 * 07_email_pipeline.sql
 * Automated email alerting pipeline for drug interactions.
 *
 * NOTE: SYSTEM$SEND_EMAIL requires a verified Snowflake user email.
 * Set one with: ALTER USER <user> SET EMAIL = '<email>'; then verify in Snowsight.
 * Once verified, create the notification integration and uncomment the send block.
 */

USE DATABASE HEALTHCARE_DW;
USE SCHEMA DDI_APP;

-- Alert generation procedure (caller's rights for automation)
CREATE OR REPLACE PROCEDURE HEALTHCARE_DW.DDI_APP.GENERATE_INTERACTION_ALERTS()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
BEGIN
    INSERT INTO HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG
        (PATIENT_ID, INTERACTION_ID, PROVIDER_ID, PROVIDER_NAME,
         SEVERITY, EMAIL_SUBJECT, EMAIL_BODY)
    SELECT
        a.PATIENT_ID, a.INTERACTION_ID, a.PRESCRIBER_A_ID, a.PRESCRIBER_A_NAME,
        a.SEVERITY,
        CONCAT('[', a.SEVERITY, ' ALERT] Drug Interaction: ',
            a.DRUG_A_NAME, ' + ', a.DRUG_B_NAME,
            ' - Patient: ', a.LAST_NAME, ', ', a.FIRST_NAME),
        AI_COMPLETE('claude-sonnet-4-6',
            CONCAT('Write a 3-paragraph medical alert email. Provider: ', a.PRESCRIBER_A_NAME,
                '. Patient: ', a.FIRST_NAME, ' ', a.LAST_NAME,
                '. Drug A: ', a.DRUG_A_NAME, '. Drug B: ', a.DRUG_B_NAME,
                '. Severity: ', a.SEVERITY,
                '. Effect: ', a.CLINICAL_EFFECT,
                '. Management: ', a.MANAGEMENT,
                '. Keep it concise and professional.'),
            OBJECT_CONSTRUCT('temperature', 0.3, 'max_tokens', 400))
    FROM HEALTHCARE_DW.DDI_APP.PATIENT_DRUG_INTERACTION_ALERTS a
    WHERE a.SEVERITY IN ('CRITICAL', 'HIGH')
      AND NOT EXISTS (
          SELECT 1 FROM HEALTHCARE_DW.DDI_APP.ALERT_EMAIL_LOG log
          WHERE log.PATIENT_ID = a.PATIENT_ID
            AND log.INTERACTION_ID = a.INTERACTION_ID
            AND log.PROVIDER_ID = a.PRESCRIBER_A_ID
      )
    LIMIT 20;

    RETURN 'Alert generation complete';
END;
$$;

-- Scheduled task (created suspended to avoid credit burn)
CREATE OR REPLACE TASK HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_ALERT_TASK
  WAREHOUSE = DEFAULT_WH
  SCHEDULE = 'USING CRON 0 */6 * * * America/Detroit'
  COMMENT = 'Generates email alert drafts for new CRITICAL and HIGH drug interactions'
AS
  CALL HEALTHCARE_DW.DDI_APP.GENERATE_INTERACTION_ALERTS();

-- To enable: ALTER TASK HEALTHCARE_DW.DDI_APP.DRUG_INTERACTION_ALERT_TASK RESUME;

-- Notification integration (uncomment after setting a verified email):
-- CREATE OR REPLACE NOTIFICATION INTEGRATION DDI_ALERT_EMAIL
--   TYPE = EMAIL
--   ENABLED = TRUE
--   ALLOWED_RECIPIENTS = ('your-verified-email@example.com');
