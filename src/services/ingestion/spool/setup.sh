#!/usr/bin/env bash
# Prepares the spool's Garage node: a layout role, the bucket and the ingestion key,
# allowed on that bucket only. Idempotent: every step checks before it changes.
#
# GARAGE is how to call the garage CLI; the default is the local Compose service.
# The bucket and the key come from the same variables the ingestion job reads.
set -euo pipefail

read -r -a garage <<<"${GARAGE:-docker compose exec -T spool-store /garage}"
bucket=${INGESTION_SPOOL__URL:?set INGESTION_SPOOL__URL}
bucket=${bucket#s3://}
bucket=${bucket%/}
key_id=${INGESTION_SPOOL__ACCESS_KEY_ID:?set INGESTION_SPOOL__ACCESS_KEY_ID}
secret=${INGESTION_SPOOL__SECRET_ACCESS_KEY:?set INGESTION_SPOOL__SECRET_ACCESS_KEY}

# A node that was just started needs a moment before it answers.
for _ in {1..30}; do
	"${garage[@]}" status >/dev/null 2>&1 && break
	sleep 1
done

if "${garage[@]}" status 2>/dev/null | grep -q 'NO ROLE ASSIGNED'; then
	node=$("${garage[@]}" node id -q 2>/dev/null)
	"${garage[@]}" layout assign -z local -c 1G "${node%%@*}"
	version=$("${garage[@]}" layout show 2>/dev/null | sed -n 's/^Current cluster layout version: //p')
	"${garage[@]}" layout apply --version $((version + 1))
fi

"${garage[@]}" bucket info "$bucket" >/dev/null 2>&1 || "${garage[@]}" bucket create "$bucket"
"${garage[@]}" key info "$key_id" >/dev/null 2>&1 ||
	"${garage[@]}" key import --yes -n ingestion "$key_id" "$secret"
"${garage[@]}" bucket allow --read --write "$bucket" --key "$key_id"
