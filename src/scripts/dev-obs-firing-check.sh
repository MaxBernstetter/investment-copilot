#!/usr/bin/env bash
# Check that the quality-warn alert fires and clears for the simulated curve ecb-aaa-spot-sim on
# the local observability profile (task dev:obs:firing-check, after task dev:obs:up). Steps:
# the scenario publishes a gap and a bad value, the processing job checks the window, Grafana
# reports quality-warn Alerting; the scenario sends a late value and a correction, the job runs
# again, and Grafana reports quality-warn Normal. The check is manual and not part of CI.
#
# Precondition: the rule must not be Alerting when the check starts. For the PR evidence run use a
# fresh stack (task dev:reset dev:up dev:obs:up). This script never runs dev:reset and can be run
# again on an existing stack: it only writes ecb-aaa-spot-sim.
#
# Usage: dev-obs-firing-check.sh
#
# Environment:
#   GRAFANA_ADMIN_PASSWORD  Grafana admin password (the Taskfile sets the local default)
#
# Each wait is bounded: the rule must appear within 60 s, each state within 300 s (polled every
# 10 s). The worst path is about 140 s: the OTLP metric export (60 s) plus the Prometheus scrape
# (15 s) plus the rule evaluation (1 m). Exit codes: 0 the check passed, 1 a step failed or timed out.
set -euo pipefail

grafana=http://127.0.0.1:${GRAFANA_PORT:-3300}
curve=ecb-aaa-spot-sim
from=2026-10-05
to=2026-10-08
rule_timeout_s=60
state_timeout_s=300
poll_s=10

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

# wait_for TIMEOUT WHAT CMD...: retry CMD every poll_s seconds, fail at the deadline.
wait_for() {
	local timeout="$1" what="$2" start=$SECONDS
	shift 2
	until "$@" >/dev/null 2>&1; do
		if ((SECONDS - start >= timeout)); then
			fail "timed out after ${timeout}s waiting for $what"
		fi
		sleep "$poll_s"
	done
	echo "ok: $what after $((SECONDS - start))s"
}

require_profile() {
	[[ -n "$(docker compose --profile observability ps --status running --quiet grafana)" ]] || fail "observability profile not running (task dev:obs:up)"
}

# rules_json: the Grafana rules of quality-warn in Prometheus format.
rules_json() {
	curl -fsSG --max-time 5 -u "admin:$GRAFANA_ADMIN_PASSWORD" "$grafana/api/prometheus/grafana/api/v1/rules" --data-urlencode rule_name=quality-warn
}

rule_loaded() {
	grep -q '"name":"quality-warn"' <<<"$(rules_json)"
}

# instance_state: the state of the curve's alert instance, or nothing when Grafana has none.
instance_state() {
	grep -oE '"labels":\{[^}]*"curve":"'"$curve"'"[^}]*\},"annotations":\{[^}]*\},"state":"[^"]*"' <<<"$(rules_json)" |
		sed -E 's/.*"state":"([^"]*)"$/\1/' | head -n 1
}

state_is() {
	[[ "$(instance_state)" == "$1" ]]
}

# scenario EVENT...: run corrected-yield on the simulated curve with these events.
scenario() {
	local args=() event
	for event in "$@"; do
		args+=(--event "$event")
	done
	docker compose --profile tools run --rm --build --entrypoint ingestion-scenario ingestion corrected-yield "${args[@]}"
}

check_job() {
	docker compose --profile tools run --rm --build processing-job "$curve" --from "$from" --to "$to"
}

echo "== step 1: rule quality-warn loaded, start state"
require_profile
wait_for "$rule_timeout_s" "rule quality-warn loaded" rule_loaded
state="$(instance_state || true)"
if [[ "$state" == Alerting ]]; then
	fail "quality-warn already Firing for $curve; run the correction (scenario late-value correction, then the check job) or use a fresh stack first"
fi
echo "start state for $curve: ${state:-none}"

echo "== step 2: gap and bad value, then the check job"
scenario publish gap bad-value
check_job

echo "== step 3: quality-warn fires"
wait_for "$state_timeout_s" "quality-warn{curve=\"$curve\"} Firing (Alerting)" state_is Alerting

echo "== step 4: late value and correction, then the check job"
scenario late-value correction
check_job

echo "== step 5: quality-warn clears"
wait_for "$state_timeout_s" "quality-warn{curve=\"$curve\"} Normal" state_is Normal

echo "firing check passed for $curve"
