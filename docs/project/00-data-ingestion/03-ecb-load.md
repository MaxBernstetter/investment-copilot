# ECB Curve Load

The first vertical slice of ingestion: it loads the ECB euro area AAA and all-issuer spot curves (11 grid tenors, 3M–30Y each) into the bitemporal core, for one valid date with a lookback window, or for a history range. The source itself is described in [[01-data-sources]]; every call goes through the [[02-source-client]].

Tracked in [#14](https://github.com/MaxBernstetter/yield-lens/issues/14). Code: `src/services/ingestion/src/ingestion/`.

## Flow

```
ingestion-load-ecb ──▶ LoadPublishedCurve ──▶ EcbSpotCurveSource ──▶ SourceClient ──▶ ECB Data Portal
   (facade/jobs)        (application)          fetch, then parse        (polite GET)
                              │                (Pandera)
                              ├──▶ OracleDeliveryStore ──▶ ing_delivery.record_delivery (ING)
                              └──▶ PersistenceClient ──▶ POST /v1/observations/versions (persistence)
```

1. The command is turned into date windows: one window for `daily`, one window per calendar year for `history`.
2. Each window costs **one** request for the whole grid (the 11 series of both instruments joined with `+`, `format=csvdata&detail=dataonly`). Windows run one after another, never in parallel.
3. The answer is stored as a raw delivery in `ING` and committed, before it is parsed ([[04-raw-deliveries]]). An answer without data is stored without payload.
4. The CSV is validated against the declared source schema, then mapped to observations.
5. The observations are written through the persistence write interface, in batches of at most 10 000, each naming its delivery (`delivery_id`). Ingestion never touches `CORE`.
   - Any `2xx` is success. `recorded_count` counts new versions, `unchanged_count` the values persistence already held (versioning, #15; read as `0` when absent).
   - `409` "Concurrent write" (two writers racing to create the first version of a key) is retried: at most 3 attempts per batch, waiting 0.5 s and 1 s. Any other error fails the run at once.
   - A batch never names an observation twice: the source schema rejects duplicate rows, and windows do not overlap.

## Commands

```sh
ingestion-load-ecb daily --valid-date 2026-10-15 [--run-id ID]
ingestion-load-ecb history --start 2004-09-06 --end 2026-10-16 [--run-id ID]
ingestion-load-ecb replay --fetched-from 2026-10-01 --fetched-to 2026-10-18 [--run-id ID]
ingestion-load-ecb fail-unfinished --run-id ID --error-type TYPE [--error-message TEXT]
```

| Command | Requests | Window |
|---|---|---|
| `daily` | 1 | `valid-date` minus the lookback (business days, Monday to Friday) up to `valid-date` |
| `history` | 1 per calendar year | Each year clipped to `start`…`end`; the full history is 23 requests |
| `replay` | 0 | The deliveries stored in `ING` that were fetched on these days (UTC), see [[04-raw-deliveries#Replay]] |

- **Run id:** defaults to a deterministic value (`ecb-daily-<date>`, `ecb-history-<start>-<end>`, `ecb-replay-<from>-<to>`), so a rerun of the same load reuses it. The daily DAG passes its own, `daily_load_ecb-<valid date>` (see [[04-daily-schedule]]).
- **Output:** one JSON line on stdout (`load_finished`, `run_id`, `attempt`, per window its `delivery_id`, delivered (and `delivered_by_curve`), recorded and unchanged counts, `known_from` per batch, the source's `Last-Modified`). `replay` prints `replay_finished` with the counts per delivery. A failure is one JSON line on stderr (`load_failed`, error type and message). The summary and failure lines carry `trace_id` and `span_id` of the run's root span `ingestion-load-ecb` (`run_id`, `operation`, `source`, `attempt`). Log lines inside a span carry the same ids.
- **Exit status:** `0` the load finished, also with zero rows; `1` the load failed (kill switch, request failed, delivery not stored, payload invalid, write rejected); `2` usage or configuration error.
- **Locally:** `devbox run -- task ingestion:load:ecb:daily VALID_DATE=2026-10-15` or `task ingestion:load:ecb:history START=… END=…` against a running persistence api (`task persistence:run`). These call the live ECB API: manual use only, never in CI.

## Configuration

Besides the source settings of the [[02-source-client#Configuration|source client]]:

| Variable | Default | Meaning |
|---|---|---|
| `INGESTION_SOURCES__ECB__LOOKBACK_BUSINESS_DAYS` | `10` | Business days before the valid date that a daily load re-fetches (≥ 0) |
| `INGESTION_PERSISTENCE__URL` | – (required) | Base URL of the persistence api, e.g. `http://localhost:8001` (the Taskfile sets this local default) |
| `INGESTION_PERSISTENCE__TIMEOUT_SECONDS` | `30` | Timeout per write request |
| `INGESTION_DB__DSN` | – (required) | Oracle DSN of the `ING` schema, e.g. `localhost:1521/FREEPDB1` (Taskfile local default) |
| `INGESTION_DB__USER` | `ing_app` | Runtime user of `ING` |
| `INGESTION_DB__PASSWORD` | – (required) | Its password (Taskfile local default; a secret elsewhere) |
| `INGESTION_DB__CALL_TIMEOUT_MS` | `30000` | Timeout per database call |

The telemetry follows the standard OpenTelemetry variables. Traces and metrics are exported over OTLP/HTTP only when an endpoint is set; without one the job runs and records nothing outside the process.

| Variable | Default | Meaning |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | none | Collector base URL, e.g. `http://localhost:4318`. None means no export |
| `OTEL_SERVICE_NAME` | `unknown_service` | Service name on every span and metric |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | `cumulative` | Temporality of the exported metrics; set `delta` for the job, which exports once at exit |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | `http` in the image | Current HTTP semantic conventions |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` | `health,ready` in the image | Probe routes that are not traced |

## Source schema (version 2)

Declared with Pandera on a Polars frame (`infrastructure/ecb/payload.py`). Every column is read as text, so the published digits are kept exactly.

| Column | Rule |
|---|---|
| `KEY` | One of the 22 grid series keys (both instruments), and equal to `YC.B.U2.EUR.4F.` + `INSTRUMENT_FM` + `.SV_C_YM.` + `DATA_TYPE_FM` |
| `FREQ`, `REF_AREA`, `CURRENCY`, `PROVIDER_FM`, `PROVIDER_FM_ID` | `B`, `U2`, `EUR`, `4F`, `SV_C_YM` |
| `INSTRUMENT_FM` | `G_N_A` (AAA) or `G_N_C` (all issuers) |
| `DATA_TYPE_FM` | `SR_3M` … `SR_30Y` (the grid) |
| `TIME_PERIOD` | ISO date `YYYY-MM-DD`, and a real calendar date |
| `OBS_VALUE` | A decimal number (no `NaN`, no exponent, not empty) |
| Rows | Unique per `INSTRUMENT_FM`, `DATA_TYPE_FM` and `TIME_PERIOD` |

Missing columns, unreadable CSV and any rule violation fail the load with `InvalidPayloadError` before any observation of that window is written; the raw delivery is already stored. Extra columns are tolerated. Quarantine and schema-drift alerts come later ([[12-data-pipeline#Source contracts and schema drift]]).

## Mapping (normalization version 2)

The rules and the recorded conventions are described in [[01-data-sources#Mapping rules]].

| Observation field | From |
|---|---|
| `curve_id` | `INSTRUMENT_FM`: `G_N_A` → `ecb-aaa-spot`, `G_N_C` → `ecb-all-spot` |
| `maturity` | `DATA_TYPE_FM` without `SR_` (`SR_10Y` → `10Y`) |
| `valid_date` | `TIME_PERIOD` |
| `value` | `OBS_VALUE`, unchanged (percent per annum) |
| `normalization_version` | `NORMALIZATION_VERSION` (`2`) |
| `origin`, `source_id`, `run_id`, `change_reason` | `published`, `ecb`, the run id, `initial` |
| `delivery_id` | The raw delivery in `ING` the window's values were parsed from |

## Empty answers

Both are a successful run with zero rows, are stored as a delivery without payload, and are never retried:

| Answer | When |
|---|---|
| `200` with an empty body | A date window without observations (weekend, holiday, before 2004, not yet published), as recorded on 2026-10-18 |
| `404` problem details "No Series was returned for the query" (or "No results found") | A query that matches nothing, e.g. `updatedAfter` without changes |

## Knowledge time

`known_from` is set by persistence when it stores a batch, also for history. The ECB's `Last-Modified` is kept as delivery metadata (in the run output and in the raw delivery, [[04-raw-deliveries]]) and is never sent as a time to persistence.

## Not yet in place

- **Reruns over stored dates rely on versioning** ([#15](https://github.com/MaxBernstetter/yield-lens/issues/15), PR [#71](https://github.com/MaxBernstetter/yield-lens/pull/71)). A daily load re-fetches its lookback window. With versioning, an unchanged value is a `200` no-op (`unchanged_count`) and a changed value becomes a new version. Without it, persistence answers `409` for dates already stored and the run fails. Ingestion does not filter on its side.
- Late-data handling ([#28](https://github.com/MaxBernstetter/yield-lens/issues/28)), conditional requests (`If-Modified-Since`), quarantine, and domain metrics beyond the request counter.

## Tests

| Test | Proves |
|---|---|
| `tests/unit/test_load_ecb_job.py` | The job end to end inside ingestion (with an in-memory delivery store): request shape (one request for both curves), raw delivery kept byte for byte and named by every value, one delivery feeding both curves, `delivered_by_curve` per window, 11 tenors per date with provenance, unchanged values, knowledge time, empty answers, history per year, malformed payload, rejected write, kill switch, configuration and usage errors, run history per attempt |
| `tests/unit/infrastructure/ecb/test_payload.py` | The declared schema against the recorded payloads (AAA only and both curves) and a set of broken ones; AAA maps as before, `G_N_C` to `ecb-all-spot`, the same tenor and date of both instruments are two observations |
| `tests/unit/infrastructure/persistence/test_client.py` | Contract requests, batching at 10 000, unchanged values, responses with and without `unchanged_count`, bounded `409` retry, other rejected writes |
| `tests/unit/infrastructure/ecb/test_source.py` | The no-data answer; a delivered answer keeps body, status, URL and `ETag`; `404`, `304` and an empty `200` are deliveries without payload |
| `tests/integration/test_delivery_store.py` | `OracleDeliveryStore` against `ING` in Oracle Free: payload byte for byte (also above 32 KB) with hash and UTC times, empty delivery, one id per delivery |
| `tests/unit/domain/test_windows.py` | Lookback and yearly windows |

Recorded ECB payloads live in `tests/fixtures/ecb/` (see `recordings.json`): a daily window, an empty window, the `404` answer and two history windows, recorded on 2026-10-18 with the source client; and a two-day window of both instruments (`mixed_*.csv`, the same request with the key `G_N_A+G_N_C`), recorded on 2026-10-22. `malformed_*.csv` is crafted. The fixtures are kept byte for byte (CRLF), so the whitespace hooks skip `tests/fixtures/` and `.gitattributes` marks them `-text`. The persistence side is a stub that validates every request against `contracts.persistence.v1`.
