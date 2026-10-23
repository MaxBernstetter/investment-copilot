#!/usr/bin/env bash
# Start or stop the whole local stack: Oracle, migrations, the four APIs, seed data and the explorer.
#
# Usage: stack.sh up|down
#   up    task dev:up, then task dev:seed unless the three real curves already have data, then the Vite dev
#         server in the background (log and pid in .task/stack/)
#   down  stops the dev server, then task dev:down (keeps the data)
#
# Environment (from .env through task): ACCESS_PORT, FRONTEND_PORT; SEED_START (default 2024-01-01)
#
# Exit codes: 0 success, 1 a step failed or the explorer did not come up, 2 usage error.
set -euo pipefail

state=.task/stack
pid_file=$state/frontend.pid
log_file=$state/frontend.log
access_url=http://127.0.0.1:${ACCESS_PORT:-8000}
frontend_url=http://localhost:${FRONTEND_PORT:-5174}

frontend_running() {
	[[ -f $pid_file ]] && kill -0 "$(<"$pid_file")" 2>/dev/null
}

up() {
	task dev:up
	seeded=1
	for curve in ecb-aaa-spot ecb-all-spot ust-par; do
		curl -fsS -o /dev/null "$access_url/v1/curves/$curve/observations" 2>/dev/null || seeded=0
	done
	if ((seeded)); then
		echo "Seed data present, skipping task dev:seed"
	else
		task dev:seed START="${SEED_START:-2024-01-01}"
	fi
	mkdir -p "$state"
	if frontend_running; then
		echo "Explorer already running"
	else
		setsid task frontend:dev >"$log_file" 2>&1 </dev/null &
		echo $! >"$pid_file"
	fi
	for _ in $(seq 60); do
		curl -fsS -o /dev/null "$frontend_url" 2>/dev/null && break
		sleep 1
	done
	curl -fsS -o /dev/null "$frontend_url" 2>/dev/null || {
		echo "Explorer did not come up on $frontend_url; see $log_file" >&2
		exit 1
	}
	echo
	echo "Explorer: $frontend_url"
	echo "API:      $access_url"
	echo "Stop:     task stack:down"
}

down() {
	if frontend_running; then
		kill -- "-$(<"$pid_file")" 2>/dev/null || true
	fi
	rm -f "$pid_file"
	task dev:down
}

case "${1:-}" in
up) up ;;
down) down ;;
*)
	echo "usage: stack.sh up|down" >&2
	exit 2
	;;
esac
