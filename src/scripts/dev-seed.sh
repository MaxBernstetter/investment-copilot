#!/usr/bin/env bash
# Seed the local development stack with ECB and US Treasury history recorded at two knowledge times, so the
# explorer can time travel: the first load covers START up to a cutoff (with a quality check
# of the three real curves), the second covers the days after it (with another check at the end),
# and the printed knowledge time lies between the two loads.
#
# Usage: dev-seed.sh START
#   START  first valid date to load, YYYY-MM-DD (required)
#
# Environment:
#   COMPOSE_FILE  docker compose's own; task dev:seed sets it (adds compose.observability.yaml
#                 while the observability profile runs)
#
# Makes live ECB and Treasury calls through the ingestion job container. Needs GNU date.
# Exit codes: 0 success, 1 a load failed, 2 usage error.
set -euo pipefail

if [[ $# -lt 1 || -z "$1" ]]; then
	echo "usage: dev-seed.sh START (YYYY-MM-DD)" >&2
	exit 2
fi
start="$1"

# Cutoff: the 20th business day counting back from yesterday (yesterday included).
yesterday=$(date -u -d yesterday +%F)
cutoff="$yesterday"
counted=0
day="$yesterday"
while :; do
	if [[ $(date -u -d "$day" +%u) -lt 6 ]]; then
		counted=$((counted + 1))
	fi
	if [[ "$counted" -eq 20 ]]; then
		cutoff="$day"
		break
	fi
	day=$(date -u -d "$day - 1 day" +%F)
done
after_cutoff=$(date -u -d "$cutoff + 1 day" +%F)

ingest() {
	docker compose --profile tools run --rm --build ingestion "$@"
	docker compose --profile tools run --rm --build --entrypoint ingestion-load-ust ingestion "$@"
}

check() {
	for curve in ecb-aaa-spot ecb-all-spot ust-par; do
		docker compose --profile tools run --rm --build processing-job "$curve" --from "$1" --to "$2"
	done
}

ingest history --start "$start" --end "$cutoff"
check "$start" "$cutoff"
sleep 2
knowledge_time=$(date -u +%FT%TZ)
echo "Knowledge time between the two loads: $knowledge_time"
echo "Try: http://localhost:${FRONTEND_PORT:-5174}/?as_of=$knowledge_time"
sleep 2
ingest history --start "$after_cutoff" --end "$yesterday"
check "$after_cutoff" "$yesterday"
