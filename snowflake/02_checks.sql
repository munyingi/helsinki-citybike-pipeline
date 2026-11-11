-- Handy checks while building. Run as TRANSFORMER (or ACCOUNTADMIN for the last two).
USE ROLE transformer;
USE WAREHOUSE citybike_wh;

-- Rows per load file
SELECT source_file, COUNT(*) AS rows_loaded
FROM citybike.raw.trips
GROUP BY source_file
ORDER BY source_file;

-- Files COPY INTO has loaded (last 14 days)
SELECT file_name, status, row_count, last_load_time
FROM TABLE(citybike.information_schema.copy_history(
  table_name => 'CITYBIKE.RAW.TRIPS',
  start_time => DATEADD(day, -14, CURRENT_TIMESTAMP())))
ORDER BY last_load_time DESC;

-- After dbt build: data quality and reconciliation
SELECT * FROM citybike.quality.quality_trip_status ORDER BY source_file, quality_status;
SELECT * FROM citybike.quality.quality_reconciliation ORDER BY year;

-- Credits used so far (needs ACCOUNTADMIN; ACCOUNT_USAGE can lag up to ~3 hours)
USE ROLE accountadmin;
SELECT warehouse_name, SUM(credits_used) AS credits
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name;

-- Resource monitor status
SHOW RESOURCE MONITORS;
