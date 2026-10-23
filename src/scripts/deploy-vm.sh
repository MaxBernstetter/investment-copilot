#!/usr/bin/env bash
# Live VM deployment steps (docs/architecture/09-deployment.md, Live VM). Run through the deploy tasks
# in src/deploy/Taskfile.vm.yml, from the checkout on the VM or from a developer machine.
#
# Usage: deploy-vm.sh config|login|pull|migrate|up|ready
#   config   validate the overlay with the env file and the Caddyfile (needs the local caddy image)
#   login    log in to GHCR with GHCR_USER and GHCR_TOKEN from the env file (read-only token)
#   pull     pull the images at the checked-out commit (YIELDLENS_TAG)
#   migrate  run the Liquibase migrations CORE, ING and PROC from the checkout, in that order
#   up       start the stack and wait until its services are healthy
#   ready    check the readiness of the four apis on 127.0.0.1; fails when one is not ready
#
# Environment:
#   YIELDLENS_ENV_FILE  the VM .env (required; /opt/yieldlens/.env on the VM, vm.env.example for config)
#
# The Compose calls run with `env -i`: no shell variable (for example a dev Taskfile default) reaches
# the VM stack; only the env file and the values this script sets are passed on.
# Exit codes: 0 success, 1 a step failed, 2 usage or configuration error.
set -euo pipefail

readonly compose_files=compose.yaml:compose.observability.yaml:compose.vm.yaml
readonly pages_origin=https://maxbernstetter.github.io
readonly caddy_image=ghcr.io/maxbernstetter/yield-lens-caddy

usage() {
	echo "usage: deploy-vm.sh config|login|pull|migrate|up|ready" >&2
	exit 2
}

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

[[ $# -eq 1 ]] || usage
step="$1"
[[ -n ${YIELDLENS_ENV_FILE:-} && -f $YIELDLENS_ENV_FILE ]] || {
	echo "YIELDLENS_ENV_FILE must name an existing file" >&2
	exit 2
}
env_file="$(realpath "$YIELDLENS_ENV_FILE")"
cd "$(dirname "$0")/../deploy"
if [[ $step == config ]]; then tag=local; else tag="$(git rev-parse HEAD)"; fi

# env_value KEY: the value of the last KEY= line in the env file (literal, no expansion).
env_value() {
	sed -n "s/^$1=//p" "$env_file" | tail -n 1
}

# compose ARGS...: docker compose with the VM files and only the env file as configuration.
compose() {
	env -i PATH="$PATH" HOME="$HOME" COMPOSE_FILE="$compose_files" YIELDLENS_TAG="$tag" \
		docker compose --env-file "$env_file" "$@"
}

check_config() {
	local config public builds cors checks
	config="$(compose --profile airflow --profile observability --profile tools config --format json)" || fail "docker compose config failed"
	public="$(jq -r '.services | to_entries[] | .key as $s | (.value.ports // [])[] | select(.host_ip != "127.0.0.1") | "\($s):\(.published)"' <<<"$config" | sort | paste -sd ' ' -)"
	[[ $public == "caddy:443 caddy:80" ]] || fail "only caddy may publish public ports (80, 443); found: ${public:-none}"
	builds="$(jq -r '.services | to_entries[] | select(.value.build) | .key' <<<"$config" | paste -sd ' ' -)"
	[[ -z $builds ]] || fail "services would build on the VM: $builds"
	cors="$(jq -r '.services.access.environment.ACCESS_CORS_ORIGINS' <<<"$config")"
	[[ $cors == "$pages_origin" ]] || fail "ACCESS_CORS_ORIGINS is $cors, expected $pages_origin"
	checks="$(jq -r '.services.access.environment.ACCESS_ALLOW_QUALITY_CHECKS // "false"' <<<"$config")"
	[[ $checks == false ]] || fail "ACCESS_ALLOW_QUALITY_CHECKS is $checks: the public API must not start quality checks"
	docker run --rm --env YIELDLENS_DOMAIN="$(env_value YIELDLENS_DOMAIN)" \
		--env YIELDLENS_ACME_EMAIL="$(env_value YIELDLENS_ACME_EMAIL)" "$caddy_image:$tag" \
		caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || fail "the Caddyfile is invalid"
}

readonly migrations=(core-migrate ing-migrate proc-migrate)
# ingestion and processing-job are deliberately not in services: they are pulled because the airflow profile
# is active, and Airflow starts them on demand.
readonly services=(oracle persistence processing access ingestion-api airflow-postgres airflow-init
	airflow-scheduler airflow-dag-processor airflow-apiserver otel-collector prometheus tempo grafana caddy)
readonly ready_ports=(8000 8001 8002 8003) # access, persistence, processing, ingestion

login() {
	local user token
	user="$(env_value GHCR_USER)"
	token="$(env_value GHCR_TOKEN)"
	[[ -n $user && -n $token ]] || {
		echo "GHCR_USER and GHCR_TOKEN must be set in $env_file" >&2
		exit 2
	}
	printf '%s' "$token" | docker login ghcr.io --username "$user" --password-stdin >/dev/null || fail "GHCR login failed"
}

pull() {
	compose --profile airflow --profile observability pull --quiet || fail "pull failed"
}

migrate() {
	local m
	for m in "${migrations[@]}"; do
		compose --profile tools run --rm "$m" || fail "migration $m failed"
	done
}

up() {
	compose --profile airflow --profile observability up --detach --wait "${services[@]}" || fail "the stack did not become healthy"
}

ready() {
	local port
	for port in "${ready_ports[@]}"; do
		curl --fail --silent --show-error --max-time 5 --retry 30 --retry-delay 2 --retry-all-errors \
			"http://127.0.0.1:$port/ready" >/dev/null || fail "the api on port $port is not ready"
	done
}

case "$step" in
config) check_config ;;
login) login ;;
pull) pull ;;
migrate) migrate ;;
up) up ;;
ready) ready ;;
*) usage ;;
esac
