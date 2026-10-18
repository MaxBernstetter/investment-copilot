# ECB Curve Load

The first vertical slice of ingestion: it loads the ECB euro area AAA spot curve (11 grid tenors, 3M–30Y) into the bitemporal core, for one valid date with a lookback window, or for a history range. The source itself is described in [[01-data-sources]]; every call goes through the [[02-source-client]].

Tracked in [#14](https://github.com/MaxBernstetter/investment-copilot/issues/14). Code: `src/services/ingestion/src/ingestion/`.

## Flow

```
ingestion-load-ecb ──▶ LoadPublishedCurve ──▶ EcbSpotCurveSource ──▶ SourceClient ──▶ ECB Data Portal
   (facade/jobs)        (application)          fetch + Pandera          (polite GET)
                              │
                              └──▶ PersistenceClient ──▶ POST /v1/observations/versions (persistence)
```

1. The command is turned into date windows: one window for `daily`, one window per calendar year for `history`.
2. Each window costs **one** request for the whole grid (the 11 series joined with `+`, `format=csvdata&detail=dataonly`). Windows run one after another, never in parallel.
3. The CSV is validated against the declared source schema, then mapped to observations.
4. The observations are written through the persistence write interface, in batches of at most 10 000. Ingestion never touches the database.
   - Any `2xx` is success. `recorded_count` counts new versions, `unchanged_count` the values persistence already held (versioning, #15; read as `0` when absent).
   - `409` "Concurrent write" (two writers racing to create the first version of a key) is retried: at most 3 attempts per batch, waiting 0.5 s and 1 s.
   - No answer, a `5xx` or a `409` after the third attempt means persistence is **unavailable**: the window goes to the spool (see [[#Persistence unavailable]]). Any other error fails the run at once.
   - A batch never names an observation twice: the source schema rejects duplicate rows, and windows do not overlap.

## Commands

```sh
ingestion-load-ecb daily --valid-date 2026-10-15 [--run-id ID]
ingestion-load-ecb history --start 2004-09-06 --end 2026-10-16 [--run-id ID]
ingestion-load-ecb drain
```

| Command | Requests | Window |
|---|---|---|
| `daily` | 1 | `valid-date` minus the lookback (business days, Monday to Friday) up to `valid-date` |
| `history` | 1 per calendar year | Each year clipped to `start`…`end`; the full history is 23 requests |
| `drain` | 0 | None: only records what the spool holds |

- **Run id:** defaults to a deterministic value (`ecb-daily-<date>`, `ecb-history-<start>-<end>`), so a rerun of the same load reuses it. Airflow ([#21](https://github.com/MaxBernstetter/investment-copilot/issues/21)) will pass its own.
- **Output:** one JSON line on stdout: `load_finished`, or `load_deferred` while data waits in the spool. It holds the delivered, recorded and unchanged counts per window, `known_from` per batch, the source's `Last-Modified`, the `spooled_windows`, and under `drained` the spooled windows recorded by this run, the `rejected` ones and `is_blocked`. A failure is one JSON line on stderr (`load_failed`, error type and message).
- **Exit status:**
  - `0` the load finished, also with zero rows.
  - `1` the load failed (kill switch, request failed, payload invalid, write rejected, spool store unreachable), or persistence refused a spooled window.
  - `2` usage or configuration error.
  - `3` deferred: persistence was unavailable, and fetched data waits in the spool. Airflow treats it as a failure, so it alerts and retries, and the retry drains the spool.
- **Locally:** `devbox run -- task ingestion:load:ecb:daily VALID_DATE=2026-10-15` or `task ingestion:load:ecb:history START=… END=…` against a running persistence api (`task persistence:run`) and spool (`task ingestion:spool:start ingestion:spool:setup`). `task ingestion:drain:ecb` runs `drain`. These call the live ECB API: manual use only, never in CI.

## Configuration

Besides the source settings of the [[02-source-client#Configuration|source client]]:

| Variable | Default | Meaning |
|---|---|---|
| `INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS` | `10` | Business days before the valid date that a daily load re-fetches (≥ 0) |
| `INGESTION_PERSISTENCE__URL` | – (required) | Base URL of the persistence api, e.g. `http://localhost:8001` (the Taskfile sets this local default) |
| `INGESTION_PERSISTENCE__TIMEOUT_SECONDS` | `30` | Timeout per write request |
| `INGESTION_SPOOL__URL` | – (required) | The spool bucket, e.g. `s3://ingestion-spool` |
| `INGESTION_SPOOL__ENDPOINT` | – (required) | S3 API of the spool store, e.g. `http://localhost:3900` |
| `INGESTION_SPOOL__REGION` | `garage` | The store's S3 region |
| `INGESTION_SPOOL__ACCESS_KEY_ID`, `INGESTION_SPOOL__SECRET_ACCESS_KEY` | – (required) | The key that may read and write the bucket (the Taskfile sets local defaults) |

## Source schema (version 1)

Declared with Pandera on a Polars frame (`infrastructure/ecb/payload.py`). Every column is read as text, so the published digits are kept exactly.

| Column | Rule |
|---|---|
| `KEY` | One of the 11 grid series keys, and equal to `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.` + `DATA_TYPE_FM` |
| `FREQ`, `REF_AREA`, `CURRENCY`, `PROVIDER_FM`, `INSTRUMENT_FM`, `PROVIDER_FM_ID` | `B`, `U2`, `EUR`, `4F`, `G_N_A`, `SV_C_YM` |
| `DATA_TYPE_FM` | `SR_3M` … `SR_30Y` (the grid) |
| `TIME_PERIOD` | ISO date `YYYY-MM-DD`, and a real calendar date |
| `OBS_VALUE` | A decimal number (no `NaN`, no exponent, not empty) |
| Rows | Unique per `DATA_TYPE_FM` and `TIME_PERIOD` |

Missing columns, unreadable CSV and any rule violation fail the load with `InvalidPayloadError` before anything of that window is written. Extra columns are tolerated. Quarantine and schema-drift alerts come later ([[12-data-pipeline#Source contracts and schema drift]]).

## Mapping (minimal)

Only what is needed to write the grid; the common maturity grid, conventions and the normalization version are [#19](https://github.com/MaxBernstetter/investment-copilot/issues/19).

| Observation field | From |
|---|---|
| `curve_id` | `ecb-aaa-spot` |
| `maturity` | `DATA_TYPE_FM` without `SR_` (`SR_10Y` → `10Y`) |
| `valid_date` | `TIME_PERIOD` |
| `value` | `OBS_VALUE`, unchanged (percent per annum) |
| `origin`, `source_id`, `run_id`, `change_reason` | `published`, `ecb`, the run id, `initial` |

## Empty answers

Both are a successful run with zero rows and are never retried:

| Answer | When |
|---|---|
| `200` with an empty body | A date window without observations (weekend, holiday, before 2004, not yet published), as recorded on 2026-10-18 |
| `404` problem details "No Series was returned for the query" (or "No results found") | A query that matches nothing, e.g. `updatedAfter` without changes |

## Persistence unavailable

When persistence cannot take a window, the window is kept in the **spool**, a Garage bucket, instead of being dropped ([[0017-ingestion-spool-on-garage]], [#80](https://github.com/MaxBernstetter/investment-copilot/issues/80)).

1. **Every run drains first.** Before it fetches anything, a run records the spooled windows oldest first, each under the run id that fetched it. A recorded window is deleted from the spool.
2. **Unavailable while draining:** the drain stops, and the rest keeps waiting.
3. **Unavailable while loading:** the window goes to the spool. The run still fetches its remaining windows (fetch once), and spools them too.
4. **Order guard:** while anything waits in the spool, new windows are spooled behind it and never written directly. A stale value recorded after a newer one would otherwise become its newer version.
5. **Refused while draining:** a `4xx` moves the window to `ecb/rejected/`, where it is kept for inspection. The drain goes on, and the run exits `1`.

- A window that was partly recorded before the outage is resent whole. Versioning ([#15](https://github.com/MaxBernstetter/investment-copilot/issues/15)) makes the values already stored unchanged no-ops.
- The knowledge time of a spooled value is when persistence finally stores it. The fetch time stays in the spool object.
- The spool store is needed by every run, because the drain lists it. If it is unreachable, the run fails with exit `1`.
- **Spool object:** `ecb/pending/<fetched_at>_<start>_<end>.parquet`. One row per observation (`value` as text, digits exact), with the delivery and run as Parquet metadata.
- **Metric:** `yl_ingestion_spool_events_total{source,event=spooled|drained|rejected}`.

## Knowledge time

`known_from` is set by persistence when it stores a batch, also for history. The ECB's `Last-Modified` is kept as delivery metadata (in the run output, and later in the raw layer, [#20](https://github.com/MaxBernstetter/investment-copilot/issues/20)) and is never sent as a time to persistence.

## Not yet in place

- **Reruns over stored dates rely on versioning** ([#15](https://github.com/MaxBernstetter/investment-copilot/issues/15), PR [#78](https://github.com/MaxBernstetter/investment-copilot/pull/78)). A daily load re-fetches its lookback window. With versioning, an unchanged value is a `200` no-op (`unchanged_count`) and a changed value becomes a new version. Without it, persistence answers `409` for dates that are already stored. The load would read that as unavailable, spool the window, and keep failing to drain it, so the spool needs #15. Ingestion does not filter on its side.
- **Change reason of a revised value:** every value is sent with `change_reason = initial`, and persistence stores it as sent. Which reason a revised value from a lookback rerun gets is open; reason derivation is [#23](https://github.com/MaxBernstetter/investment-copilot/issues/23).
- Raw payload retention ([#20](https://github.com/MaxBernstetter/investment-copilot/issues/20)), normalization ([#19](https://github.com/MaxBernstetter/investment-copilot/issues/19)), scheduling ([#21](https://github.com/MaxBernstetter/investment-copilot/issues/21)), the backfill feature ([#27](https://github.com/MaxBernstetter/investment-copilot/issues/27)), late-data handling ([#28](https://github.com/MaxBernstetter/investment-copilot/issues/28)), conditional requests (`If-Modified-Since`), quarantine, run records in the transparency interface and domain metrics beyond the request counter.

## Tests

| Test | Proves |
|---|---|
| `tests/unit/test_load_ecb_job.py` | The job end to end inside ingestion: request shape, 11 tenors per date with provenance, unchanged values, knowledge time, empty answers, history per year, malformed payload, rejected write, kill switch, configuration and usage errors; with persistence unavailable: deferral, drain order, the order guard, `drain` and refused spool windows |
| `tests/unit/infrastructure/spool/test_object_store.py` | The spool on in-memory and local stores: round trip with exact digits, fetch order, remove, reject, format guard, metric |
| `tests/integration/test_spool_on_garage.py` | The spool against a real Garage node, prepared by `spool/setup.sh` |
| `tests/unit/infrastructure/ecb/test_payload.py` | The declared schema against the recorded payload and a set of broken ones |
| `tests/unit/infrastructure/persistence/test_client.py` | Contract requests, batching at 10 000, unchanged values, responses with and without `unchanged_count`, bounded `409` retry, other rejected writes |
| `tests/unit/domain/test_windows.py` | Lookback and yearly windows |

Recorded ECB payloads live in `tests/fixtures/ecb/` (see `recordings.json`): a daily window, an empty window, the `404` answer and two history windows, recorded on 2026-10-18 with the source client. `malformed_*.csv` is crafted. The fixtures are kept byte for byte (CRLF), so the whitespace hooks skip `tests/fixtures/` and `.gitattributes` marks them `-text`. The persistence side is a stub that validates every request against `contracts.persistence.v1`.
