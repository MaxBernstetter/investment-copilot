#!/bin/sh
# Copy every service's observability folders into the volumes Grafana provisions from. Runs in
# the grafana-provisioning service (task dev:obs:up) before Grafana starts.
#
# Layout written:
#   /out/alerting/<service>-<file>.yaml   alert rule files, flat (Grafana reads one directory)
#   /out/dashboards/<service>/<file>.json dashboards, one folder per service
#
# A missing or empty service folder is skipped. Both output volumes are emptied first, so
# deleted files disappear on the next dev:obs:up.
# Adding a service: append its name to services below. That is the only change needed.
#
# Environment: none. Exit codes: 0 always when the copy runs; 1 on a shell error (set -e).
set -eu

services="processing ingestion"
src=/yieldlens/services
alerting=/out/alerting
dashboards=/out/dashboards

find "$alerting" "$dashboards" -mindepth 1 -delete

for service in $services; do
	alerts=0
	for file in "$src/$service/observability/alerts/"*.yaml; do
		[ -f "$file" ] || continue
		cp "$file" "$alerting/$service-$(basename "$file")"
		alerts=$((alerts + 1))
	done
	boards=0
	for file in "$src/$service/observability/dashboards/"*.json; do
		[ -f "$file" ] || continue
		mkdir -p "$dashboards/$service"
		cp "$file" "$dashboards/$service/"
		boards=$((boards + 1))
	done
	echo "grafana-provisioning: $service: $alerts alert files, $boards dashboards"
done
