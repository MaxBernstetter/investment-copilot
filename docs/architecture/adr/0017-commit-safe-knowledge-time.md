# ADR 0017: Commit-safe knowledge time

**Status:** Accepted · 2026-10-19

## Context
An as-of read (`get_as_of`, `get_series`) must return the same answer for a knowledge time `t` forever. Until now `record_versions` took its knowledge time from the database clock after locking only the open versions of its own batch. Two writers of different observations do not block each other, so a writer that read the clock first could commit after a writer that read it later. A reader that picked `t` between the two commits saw the later commit's version appear at a knowledge time it had already served. A CodeRabbit review finding on #117 pointed at this gap.

## Options

| Option | For | Against |
|---|---|---|
| **Global knowledge clock: one row, locked by every write** | Knowledge times strictly increase in commit order; the committed horizon is a watermark a reader can use safely; small change inside the package | Writes serialize on one row; a single writer at a time for the whole store |
| Lock per curve (or per curve and valid-date range) | Writers of different curves run in parallel | Still needs an ordering across curves for a safe global watermark; the watermark becomes per curve and every reader must know it |
| Serializable isolation or `SELECT ... FOR UPDATE` on the whole table | No new table | Coarser lock than one row; readers are affected; the ordering still depends on the clock read |
| Knowledge time from a sequence instead of the clock | Strictly increasing values | Not tied to a time of day; the sequence order still differs from commit order unless writers serialize |

## Decision
- A single-row table `knowledge_clock` holds the **knowledge horizon**: the knowledge time of the latest committed call. It is seeded with the newest `known_from` of `observation` (1970 when empty).
- Every `record_versions` call locks that row first, then reads the horizon. Its knowledge time is `p_known_from` if given (it must be after the horizon, else `-20004`), otherwise the database clock, moved to one microsecond after the horizon if the clock lags behind it.
- The call moves the horizon to its knowledge time when it stores its batch. A failed call rolls the move back with its batch.
- `knowledge_horizon()` returns the committed horizon. A reader that uses it as its as-of time gets an answer that no later commit can change.

## Consequences
- Writes serialize on the clock row. This fits the daily batch loads of phase 1; the persistence service is not on a high-frequency write path.
- Knowledge times are unique and increase in commit order, so every version has a clear place in the timeline. A value can be known a few microseconds after the database clock says, when writes come in quick succession.
- The horizon is the read watermark for consumers. Clients that need "the latest state" still read the current horizon; clients that replay a past state keep their as-of time.
- The clock is the scaling lever. When writes outgrow one row, the clock can move to one row per curve. Readers then need a watermark per curve, and that change needs its own ADR.
- Tests that pass a fixed knowledge time must pass one after the horizon; the utPLSQL suite resets the clock to 1970 for that reason.
