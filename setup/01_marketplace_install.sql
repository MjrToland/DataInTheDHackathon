/*
 * 01_marketplace_install.sql
 * Install Marketplace listings for drug interaction and adverse event data.
 *
 * NOTE: Marketplace listings must be installed manually via the Snowsight UI
 * or the GET command. After installation, run the grants below.
 *
 * Listings:
 *   - DrugBank Biomedical Knowledge (GZTYZJ6Q7W0)
 *     -> Database: BIOMEDICAL_KNOWLEDGE_PACKAGE
 *     -> Key tables: DRUG_INTERACTIONS, ADVERSE_EFFECTS, DRUGS, DRUG_INDICATIONS
 *
 *   - FDA FAERS Adverse Event Reports (GZ2FWZ5FDDY)
 *     -> Database: FDA_FAERS_ADVERSE_EVENT_REPORTS
 *     -> Key tables: DEMO, DRUG, REAC, OUTC, INDI, THER
 */

-- Step 1: Install via Snowsight Marketplace UI
--   Navigate to: Marketplace -> Search "DrugBank Biomedical Knowledge"
--   Click "Get" or "Request" to install
--   Repeat for "FDA FAERS Adverse Event Reports"

-- Step 2: After installation, grant access to the role used by the app
USE ROLE ACCOUNTADMIN;

-- Grant usage on DrugBank (adjust database name if different after install)
GRANT IMPORTED PRIVILEGES ON DATABASE BIOMEDICAL_KNOWLEDGE_PACKAGE
  TO ROLE DRUG_INTERACTION_APP_ROLE;

-- Grant usage on FDA FAERS (adjust database name if different after install)
GRANT IMPORTED PRIVILEGES ON DATABASE FDA_FAERS_ADVERSE_EVENT_REPORTS
  TO ROLE DRUG_INTERACTION_APP_ROLE;

-- Verify access
-- SHOW TABLES IN DATABASE BIOMEDICAL_KNOWLEDGE_PACKAGE;
-- SHOW TABLES IN DATABASE FDA_FAERS_ADVERSE_EVENT_REPORTS;
