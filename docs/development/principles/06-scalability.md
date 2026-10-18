# Scalability

Design every piece so it would work at **100× the data volume**, without building the 100× infrastructure today. The platform levers are described in `docs/architecture/08-scalability.md`. This note covers what each piece must do.

## Rules for every piece

- **Set-based, not row-by-row:** process data in bulk (SQL, `FORALL`, Arrow batches, vectorized code). Loops over individual observations are a red flag.
- **Chunkable:** long operations take a date range and can be split into independent chunks that run in parallel.
- **Bounded memory:** stream or page large results; never load a full history into memory.
- **Stateless and idempotent:** any instance can handle any request or chunk, and reruns are safe (see [[01-twelve-factor]]).
- **Query by partition key:** queries on observations filter by `valid_date` (and knowledge time), so partition pruning works.
- **Low-cardinality telemetry:** metric labels never contain ids or dates.
- **Bounded APIs:** list endpoints are paginated; bulk transfers use the Arrow bulk interface.

## Balance with simplicity

Scalability is a **design property**, not an extra feature (see [[03-simplicity]]):

- **Do:** choose the shape that scales (bulk, chunked, stateless) when it costs about the same as the shape that doesn't.
- **Don't:** add caches, queues, sharding or extra infrastructure until a measured need exists.

## Self-check before merging

- What happens to runtime and memory if the input is 100× larger?
- Can this run in parallel chunks without coordination?
- Does any query scan the full history unnecessarily?
