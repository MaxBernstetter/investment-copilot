# 01 Data Persistence

Data persistence stores every value with its full history. The `persistence` service owns the `CORE` schema and gives each observation a valid time and a knowledge time. Corrections and late data add versions instead of overwriting, so any past state can be retrieved as it was known at the time.

## Notes

- [[01-bitemporal-model]]: the two time axes, the `observation` table and reference data
- [[02-persistence-service]]: the REST interface of the persistence service and its responses
