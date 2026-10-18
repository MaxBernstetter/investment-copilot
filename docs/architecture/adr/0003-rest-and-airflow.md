# ADR 0003: REST interfaces and Airflow orchestration, no message broker

**Status:** Accepted · 2026-10-18 · Amended by [[0010-api-and-job-process-types]] (heavy batch work runs as ephemeral job containers)

## Context
The pipeline is batch-oriented: a daily load plus on-demand backfill and recalculation. Services need strongly defined interfaces. The target role uses REST APIs and Apache Airflow.

## Decision
- Services communicate via **versioned REST (OpenAPI)**, with streamed Arrow endpoints for bulk data.
- **Apache Airflow** orchestrates the pipeline by calling those interfaces. DAGs hold no business logic.
- No message broker.

## Consequences
- One interface style; easy to test, document and observe. Matches the role's stack.
- Pipeline dependencies, retries and backfills are visible in Airflow.
- Coupling is temporal (synchronous calls). It is mitigated by idempotent writes, retries and async run resources (`202` + polling).
- A broker can be added later for real-time events without changing the domain models.

Rejected: Kafka/RabbitMQ. They add infrastructure without a real-time requirement.
