-- =====================================================================
-- Helsinki City Bike Pipeline: one-time Snowflake setup
-- Run in a Snowsight SQL worksheet as ACCOUNTADMIN (the trial user has it).
-- Safe to re-run: creates use IF NOT EXISTS (the monitor is replaced).
-- =====================================================================

USE ROLE ACCOUNTADMIN;

-- 1. Cost guardrail: stop compute after 20 credits.
CREATE OR REPLACE RESOURCE MONITOR citybike_monitor
  WITH CREDIT_QUOTA = 20
  FREQUENCY = NEVER
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

-- 2. Small warehouse that turns itself off after 60 seconds idle.
CREATE WAREHOUSE IF NOT EXISTS citybike_wh
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

ALTER WAREHOUSE citybike_wh SET RESOURCE_MONITOR = citybike_monitor;

-- 3. Database and schemas (raw -> staging/marts are built by dbt).
CREATE DATABASE IF NOT EXISTS citybike;
CREATE SCHEMA IF NOT EXISTS citybike.raw;

-- 4. Least-privilege role for dbt and the loader scripts.
CREATE ROLE IF NOT EXISTS transformer;
GRANT USAGE, OPERATE ON WAREHOUSE citybike_wh TO ROLE transformer;
GRANT USAGE, CREATE SCHEMA ON DATABASE citybike TO ROLE transformer;
GRANT ALL ON SCHEMA citybike.raw TO ROLE transformer;
GRANT ALL ON FUTURE TABLES IN SCHEMA citybike.raw TO ROLE transformer;
GRANT ALL ON FUTURE STAGES IN SCHEMA citybike.raw TO ROLE transformer;
GRANT ALL ON FUTURE FILE FORMATS IN SCHEMA citybike.raw TO ROLE transformer;

-- 5. Service user for dbt + Python.
--    Snowflake no longer allows password-only logins for service users,
--    so this user signs in with a key pair (TYPE = SERVICE, no password).
--    Generate the keys first:  python scripts/make_keypair.py
--    then paste the printed public key below (one line, no BEGIN/END lines).
CREATE USER IF NOT EXISTS dbt_user
  TYPE = SERVICE
  DEFAULT_ROLE = transformer
  DEFAULT_WAREHOUSE = citybike_wh;

ALTER USER dbt_user SET RSA_PUBLIC_KEY = 'PASTE_PUBLIC_KEY_HERE';   -- if you re-run this file later, skip this line

GRANT ROLE transformer TO USER dbt_user;
-- Granting to SYSADMIN puts the role under ACCOUNTADMIN in the hierarchy,
-- so you can switch to it (USE ROLE below) and see its objects in Snowsight.
GRANT ROLE transformer TO ROLE SYSADMIN;

-- 6. Raw objects, owned by the transformer role.
USE ROLE transformer;
USE WAREHOUSE citybike_wh;
USE SCHEMA citybike.raw;

CREATE FILE FORMAT IF NOT EXISTS csv_gz
  TYPE = CSV
  COMPRESSION = GZIP
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL', 'nan', 'NaN')
  EMPTY_FIELD_AS_NULL = TRUE;

CREATE STAGE IF NOT EXISTS landing
  FILE_FORMAT = csv_gz
  COMMENT = 'Normalised CSV files written by ingestion/*.py';

-- Trips are loaded as text on purpose: typing and cleaning happen in dbt,
-- so a bad value never breaks the load.
CREATE TABLE IF NOT EXISTS trips (
  departure              VARCHAR,
  return_time            VARCHAR,
  departure_station_id   VARCHAR,
  departure_station_name VARCHAR,
  return_station_id      VARCHAR,
  return_station_name    VARCHAR,
  covered_distance_m     VARCHAR,
  duration_sec           VARCHAR,
  source_file            VARCHAR,
  loaded_at              TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS weather_daily (
  obs_date     VARCHAR,
  fmisid       VARCHAR,
  parameter    VARCHAR,
  value        VARCHAR,
  source_file  VARCHAR,
  loaded_at    TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Check
SHOW TABLES IN SCHEMA citybike.raw;
