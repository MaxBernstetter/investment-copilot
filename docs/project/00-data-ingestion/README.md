# 00 Data Ingestion

Data ingestion brings source data into the platform, reliably and repeatably. It fetches a published curve from a public source through a polite client, normalizes it to the common maturity grid, and keeps every raw answer byte for byte, so each stored value can be traced to its delivery. Scheduled runs retry transient failures, and reruns and backfills are idempotent.

## Notes

- [[01-data-sources]]: the public source used in phase 1 and its publication timing
- [[02-source-client]]: the HTTP client every source adapter uses, enforcing the access policy
- [[03-ecb-load]]: the first vertical slice that loads the ECB curve into the bitemporal core
- [[04-daily-schedule]]: the Airflow DAG that runs the daily load on TARGET business days
- [[04-raw-deliveries]]: the raw bronze stage in the `ING` schema, kept for traceability
- [[05-scenarios]]: scenario events that write a simulated curve in steps (gaps, bad values, late values, corrections)
- [[06-run-history]]: recorded attempts of daily, history and replay jobs in `ING.run`
