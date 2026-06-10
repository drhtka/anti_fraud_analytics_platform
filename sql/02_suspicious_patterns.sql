-- Suspicious pattern queries for IEEE-CIS Fraud Detection.
-- Keep only one SELECT active while learning with scripts/run_duckdb_sql.py.
--
-- Proxy mapping used in this file:
-- - customer_id -> card1 (customer-like card proxy, use carefully)
-- - transaction_time -> TransactionDT (relative time in seconds, not a true timestamp)
-- - amount -> TransactionAmt
-- - device_id -> DeviceInfo / DeviceType from train_identity
-- - region -> addr1 (region-like encoded proxy)
-- - merchant_category -> ProductCD (business segment proxy)
CREATE OR REPLACE VIEW train_transaction AS
SELECT *
FROM read_csv_auto('data/train_transaction.csv', header = true);
CREATE OR REPLACE VIEW train_identity AS
SELECT *
FROM read_csv_auto('data/train_identity.csv', header = true);
CREATE OR REPLACE VIEW train_tx_identity AS
SELECT t.*,
  i.DeviceType,
  i.DeviceInfo
FROM train_transaction t
  LEFT JOIN train_identity i USING (TransactionID);
-- 1. Frequent transactions within the same relative hour for a customer proxy.
-- SELECT
--     card1 AS customer_proxy,
--     FLOOR(TransactionDT / 3600) AS hour_bucket,
--     COUNT(*) AS tx_count,
--     SUM(TransactionAmt) AS total_amount
-- FROM train_transaction
-- GROUP BY card1, FLOOR(TransactionDT / 3600)
-- HAVING COUNT(*) >= 5
-- ORDER BY tx_count DESC, total_amount DESC;
-- 2. Unusually large transactions relative to a customer proxy baseline.
-- WITH customer_stats AS (
--   SELECT card1 AS customer_proxy,
--     AVG(TransactionAmt) AS avg_amount,
--     STDDEV_SAMP(TransactionAmt) AS std_amount
--   FROM train_transaction
--   GROUP BY card1
-- )
-- SELECT t.TransactionID,
--   t.card1 AS customer_proxy,
--   t.TransactionAmt,
--   s.avg_amount,
--   s.std_amount
-- FROM train_transaction t
--   JOIN customer_stats s ON t.card1 = s.customer_proxy
-- WHERE t.TransactionAmt > s.avg_amount + 3 * COALESCE(s.std_amount, 0)
-- ORDER BY t.TransactionAmt DESC;
-- 3. One customer proxy uses many devices.
-- SELECT card1 AS customer_proxy,
--   COUNT(
--     DISTINCT COALESCE(DeviceType, 'unknown_type') || '|' || COALESCE(DeviceInfo, 'unknown_device')
--   ) AS distinct_devices,
--   COUNT(*) AS tx_count
-- FROM train_tx_identity
-- GROUP BY card1
-- HAVING COUNT(
--     DISTINCT COALESCE(DeviceType, 'unknown_type') || '|' || COALESCE(DeviceInfo, 'unknown_device')
--   ) >= 3
-- ORDER BY distinct_devices DESC,
--   tx_count DESC;
-- 4. One device is used by many customer proxies.
-- SELECT COALESCE(DeviceType, 'unknown_type') || '|' || COALESCE(DeviceInfo, 'unknown_device') AS device_key,
--   COUNT(DISTINCT card1) AS distinct_customer_proxies,
--   COUNT(*) AS tx_count
-- FROM train_tx_identity
-- GROUP BY device_key
-- HAVING COUNT(DISTINCT card1) >= 3
-- ORDER BY distinct_customer_proxies DESC,
--   tx_count DESC;
-- 5. Suspicious region-like and product segment combinations.
-- SELECT addr1 AS region_proxy,
--   ProductCD AS product_segment,
--   COUNT(*) AS tx_count,
--   SUM(
--     CASE
--       WHEN isFraud = 1 THEN 1
--       ELSE 0
--     END
--   ) AS fraud_tx_count,
--   ROUND(
--     100.0 * SUM(
--       CASE
--         WHEN isFraud = 1 THEN 1
--         ELSE 0
--       END
--     ) / COUNT(*),
--     2
--   ) AS fraud_rate_pct
-- FROM train_transaction
-- GROUP BY addr1,
--   ProductCD
-- HAVING COUNT(*) >= 20
-- ORDER BY fraud_rate_pct DESC,
--   tx_count DESC;
-- 6. Region changes for the same customer proxy within one hour.
SELECT customer_proxy,
  TransactionID,
  TransactionDT,
  region_proxy,
  prev_region,
  dt_delta_seconds
FROM (
    SELECT TransactionID,
      card1 AS customer_proxy,
      TransactionDT,
      addr1 AS region_proxy,
      LAG(addr1) OVER (
        PARTITION BY card1
        ORDER BY TransactionDT
      ) AS prev_region,
      TransactionDT - LAG(TransactionDT) OVER (
        PARTITION BY card1
        ORDER BY TransactionDT
      ) AS dt_delta_seconds
    FROM train_transaction
  ) region_changes
WHERE prev_region IS NOT NULL
  AND region_proxy IS NOT NULL
  AND prev_region != region_proxy
  AND dt_delta_seconds <= 3600
ORDER BY dt_delta_seconds ASC,
  customer_proxy;