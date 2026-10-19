#!/usr/bin/env bash
# Seed the local development stack with ECB history recorded at two knowledge times, so the
# explorer can time travel: the first load covers START up to a cutoff, the second covers the
# days after it, and the printed knowledge time lies between the two loads.
#
# Usage: dev-seed.sh START
#   START  first valid date to load, YYYY-MM-DD (required)
#
# Environment:
#   DEV_COMPOSE_FILE  compose file of the local stack (default: compose.yaml, relative to the
#                     working directory; `task dev:seed` runs from src/deploy)
#
# Makes live ECB calls through the ingestion job container. Needs GNU date.
# Exit codes: 0 success, 1 a load failed, 2 usage error.
set -euo pipefail

if [[ $# -lt 1 || -z "$1" ]]; then
	echo "usage: dev-seed.sh START (YYYY-MM-DD)" >&2
	exit 2
fi
start="$1"
compose_file="${DEV_COMPOSE_FILE:-compose.yaml}"

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
	docker compose -f "$compose_file" --profile tools run --rm ingestion "$@"
}

ingest history --start "$start" --end "$cutoff"
sleep 2
knowledge_time=$(date -u +%FT%TZ)
echo "Knowledge time between the two loads: $knowledge_time"
echo "Try: http://localhost:5173/?as_of=$knowledge_time"
sleep 2
ingest history --start "$after_cutoff" --end "$yesterday"
