#!/usr/bin/env bats
# Tests of src/scripts/deploy-vm.sh with fake docker and curl first on PATH (task deploy:test:unit).
# The fakes find their state directory from their own path, because `env -i` clears test variables.

readonly OK_CONFIG='{"services":{"access":{"environment":{"ACCESS_CORS_ORIGINS":"https://maxbernstetter.github.io"},"ports":[{"host_ip":"127.0.0.1","target":8000,"published":"8000"}]},"caddy":{"ports":[{"target":80,"published":"80"},{"target":443,"published":"443"}]}}}'

setup() {
	script="$BATS_TEST_DIRNAME/../deploy-vm.sh"
	mkdir -p "$BATS_TEST_TMPDIR/bin"
	export PATH="$BATS_TEST_TMPDIR/bin:$PATH"

	cat >"$BATS_TEST_TMPDIR/bin/docker" <<'FAKE'
#!/usr/bin/env bash
state="$(cd "$(dirname "$0")/.." && pwd)"
echo "$*" >>"$state/docker.log"
if [[ $1 == compose ]]; then env >"$state/docker.env"; fi
if [[ $1 == login ]]; then cat >"$state/login.stdin"; fi
if [[ -f $state/fail.pattern && "$*" == *"$(cat "$state/fail.pattern")"* ]]; then exit 1; fi
if [[ $* == *"config --format json" ]]; then cat "$state/config.json"; fi
FAKE

	cat >"$BATS_TEST_TMPDIR/bin/curl" <<'FAKE'
#!/usr/bin/env bash
state="$(cd "$(dirname "$0")/.." && pwd)"
for url; do :; done
echo "$url" >>"$state/curl.log"
if [[ -f $state/curl.fail && "$url" == *"$(cat "$state/curl.fail")"* ]]; then exit 22; fi
FAKE
	chmod +x "$BATS_TEST_TMPDIR/bin/docker" "$BATS_TEST_TMPDIR/bin/curl"

	printf '%s\n' \
		'GHCR_USER=robot' \
		'GHCR_TOKEN=s3cret' \
		'YIELDLENS_DOMAIN=example.duckdns.org' \
		'YIELDLENS_ACME_EMAIL=ops@example.org' >"$BATS_TEST_TMPDIR/vm.env"
	export YIELDLENS_ENV_FILE="$BATS_TEST_TMPDIR/vm.env"
	write_config "$OK_CONFIG"
}

# write_config JSON: the output of `docker compose ... config --format json` for the fake docker.
write_config() {
	printf '%s' "$1" >"$BATS_TEST_TMPDIR/config.json"
}

@test "no argument exits 2" {
	run "$script"
	[ "$status" -eq 2 ]
}

@test "a missing env file exits 2" {
	export YIELDLENS_ENV_FILE="$BATS_TEST_TMPDIR/missing.env"
	run "$script" config
	[ "$status" -eq 2 ]
}

@test "config passes with the overlay, the profiles and the Caddyfile check" {
	run "$script" config
	[ "$status" -eq 0 ]
	grep -qF "compose --env-file $BATS_TEST_TMPDIR/vm.env --profile airflow --profile observability --profile tools config --format json" "$BATS_TEST_TMPDIR/docker.log"
	grep -qF "run --rm" "$BATS_TEST_TMPDIR/docker.log"
	grep -qF "yield-lens-caddy:local caddy validate" "$BATS_TEST_TMPDIR/docker.log"
}

@test "config fails when grafana publishes a port on all interfaces" {
	write_config "$(jq -c '.services.grafana = {ports: [{target: 3000, published: "3300"}]}' <<<"$OK_CONFIG")"
	run "$script" config
	[ "$status" -eq 1 ]
	[[ $output == *"grafana:3300"* ]]
}

@test "config fails when a service would build on the VM" {
	write_config "$(jq -c '.services.access.build = {context: "."}' <<<"$OK_CONFIG")"
	run "$script" config
	[ "$status" -eq 1 ]
	[[ $output == *"access"* ]]
}

@test "config fails when CORS is not the Pages origin" {
	write_config "$(jq -c '.services.access.environment.ACCESS_CORS_ORIGINS = "http://localhost:5174"' <<<"$OK_CONFIG")"
	run "$script" config
	[ "$status" -eq 1 ]
}

@test "compose runs with a clean environment and the VM tag" {
	export PERSISTENCE_DB_PASSWORD=LocalApp_1
	run "$script" config
	[ "$status" -eq 0 ]
	run grep -q '^PERSISTENCE_DB_PASSWORD=' "$BATS_TEST_TMPDIR/docker.env"
	[ "$status" -eq 1 ]
	grep -qx 'COMPOSE_FILE=compose.yaml:compose.observability.yaml:compose.vm.yaml' "$BATS_TEST_TMPDIR/docker.env"
	grep -qx 'YIELDLENS_TAG=local' "$BATS_TEST_TMPDIR/docker.env"
}
