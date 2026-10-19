# 04 Data Access

Data access serves data to downstream systems and the frontend. The `access` service is the public, read-only API of YieldLens and the only service the frontend calls. Every data endpoint accepts an as-of parameter and returns version and lineage metadata with the data.

## Notes

- [[01-access-service]]: the read-only API for curves as of a knowledge time, plus health and readiness endpoints
