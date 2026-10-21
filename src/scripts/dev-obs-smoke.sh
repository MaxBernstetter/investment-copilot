#!/usr/bin/env bash
# Check the local observability profile (task dev:obs:up): the apis and jobs get their OTEL_*
# settings, Grafana provisions its datasources, dashboards and alert rules, and telemetrygen metrics and a trace reach
# Prometheus and Tempo. Run it after dev:obs:up; task dev:obs:smoke runs it from src/deploy.
#
# Usage: dev-obs-smoke.sh
#
# Environment:
#   GRAFANA_ADMIN_PASSWORD  Grafana admin password (the Taskfile sets the local default)
#
# Uses only curl, grep and docker. Exit codes: 0 all checks pass, 1 a check failed or timed out.
set -euo pipefail

telemetrygen=ghcr.io/open-telemetry/opentelemetry-collector-contrib/telemetrygen:v0.163.0
network=yieldlens-dev_default
prometheus=http://127.0.0.1:9090
tempo=http://127.0.0.1:3200
grafana=http://127.0.0.1:3300
timeout_s=90
service="yl-obs-smoke-$(date +%s)"

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

# wait_for WHAT CMD...: retry CMD every 3 s until it succeeds, fail at the deadline.
wait_for() {
	local what="$1"
	shift
	local deadline=$((SECONDS + timeout_s))
	until "$@" >/dev/null 2>&1; do
		if ((SECONDS >= deadline)); then
			fail "timed out waiting for $what"
		fi
		sleep 3
	done
	echo "ok: $what"
}

has_api_env() {
	local svc="$1" name="$2" env_out
	env_out=$(docker compose exec -T "$svc" env)
	grep -qx "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318" <<<"$env_out" &&
		grep -qx "OTEL_SERVICE_NAME=$name" <<<"$env_out"
}

has_job_env() {
	local svc="$1" name="$2" env_out
	env_out=$(docker compose --profile tools run --rm --no-deps --entrypoint env "$svc")
	grep -qx "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318" <<<"$env_out" &&
		grep -qx "OTEL_SERVICE_NAME=$name" <<<"$env_out" &&
		grep -qx "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta" <<<"$env_out"
}

check_apis() {
	local pair svc name
	for pair in persistence:persistence-api processing:processing-api access:access-api ingestion-api:ingestion-api; do
		svc="${pair%%:*}"
		name="${pair#*:}"
		has_api_env "$svc" "$name" || fail "$svc has no OTEL_* settings for $name"
		echo "ok: $name OTEL_* wiring"
	done
}

check_jobs() {
	local pair svc name
	for pair in ingestion:ingestion-job processing-job:processing-job; do
		svc="${pair%%:*}"
		name="${pair#*:}"
		has_job_env "$svc" "$name" || fail "$svc has no OTEL_* settings for $name (is the observability profile up (task dev:obs:up)?)"
		echo "ok: $name OTEL_* wiring"
	done
}

check_grafana_port() {
	[[ "$(docker compose --profile observability port grafana 3000)" == 127.0.0.1:3300 ]] || fail "Grafana is not published on 127.0.0.1:3300"
	echo "ok: Grafana on 127.0.0.1:3300"
}

prometheus_ready() {
	curl -fsS --max-time 5 -o /dev/null "$prometheus/-/ready"
}

tempo_ready() {
	curl -fsS --max-time 5 -o /dev/null "$tempo/ready"
}

grafana_datasource() {
	curl -fsS --max-time 5 -o /dev/null -u "admin:$GRAFANA_ADMIN_PASSWORD" "$grafana/api/datasources/uid/$1"
}

grafana_dashboard() {
	curl -fsS --max-time 5 -o /dev/null -u "admin:$GRAFANA_ADMIN_PASSWORD" "$grafana/api/dashboards/uid/processing"
}

grafana_rule() {
	curl -fsS --max-time 5 -o /dev/null -u "admin:$GRAFANA_ADMIN_PASSWORD" "$grafana/api/v1/provisioning/alert-rules/processing-quality-warn"
}

check_retention() {
	local flags
	flags=$(curl -fsS --max-time 5 "$prometheus/api/v1/status/flags")
	grep -q '"storage.tsdb.retention.time":"15d"' <<<"$flags" || fail "Prometheus retention is not 15d"
	echo "ok: Prometheus retention 15d"
}

# telemetrygen v0.163.0 with --metrics 3 (Sum, delta) adds 3 to the cumulative sum per run: each
# point has value 1 (measured on the local stack).
per_run_sum=3

sum_covers_both_runs() {
	local result value
	result=$(curl -fsSG --max-time 5 "$prometheus/api/v1/query" --data-urlencode "query=sum({__name__=~\"yl_obs_smoke.*\",job=\"$service\"})")
	value=$(sed -nE 's/.*"value":\[[0-9.]+,"([0-9.]+)"\].*/\1/p' <<<"$result")
	[[ -n "$value" ]] && awk -v v="$value" -v min="$((2 * per_run_sum))" 'BEGIN { exit !(v + 0 >= min) }'
}

metric_visible() {
	local result
	result=$(curl -fsSG --max-time 5 "$prometheus/api/v1/query" --data-urlencode "query=count({__name__=~\"yl_obs_smoke.*\",job=\"$service\",instance!~\"run-.*\"})")
	grep -qE '"value":\[[0-9.]+,"1"\]' <<<"$result"
}

trace_visible() {
	local result
	result=$(curl -fsSG --max-time 5 "$tempo/api/search" --data-urlencode "q={resource.service.name=\"$service\"}")
	grep -q '"traceID"' <<<"$result"
}

check_metrics() {
	local run
	for run in 1 2; do
		docker run --rm --network "$network" "$telemetrygen" metrics \
			--otlp-endpoint otel-collector:4317 --otlp-insecure \
			--service "$service" \
			--otlp-attributes "service.instance.id=\"run-$run\"" \
			--otlp-metric-name yl_obs_smoke --metric-type Sum --aggregation-temporality delta \
			--metrics 3
	done
	wait_for "metrics of runs 1 and 2 in Prometheus" metric_visible
	wait_for "sum of both runs in Prometheus" sum_covers_both_runs
}

check_trace() {
	docker run --rm --network "$network" "$telemetrygen" traces \
		--otlp-endpoint otel-collector:4317 --otlp-insecure \
		--service "$service" --traces 1
	wait_for "trace of $service in Tempo" trace_visible
}

check_apis
check_jobs
check_grafana_port
wait_for "Prometheus ready" prometheus_ready
wait_for "Tempo ready" tempo_ready
wait_for "Grafana datasource prometheus" grafana_datasource prometheus
wait_for "Grafana datasource tempo" grafana_datasource tempo
wait_for "Grafana dashboard processing" grafana_dashboard
wait_for "Grafana alert rule processing-quality-warn" grafana_rule
check_retention
check_metrics
check_trace
echo "smoke passed for $service"
