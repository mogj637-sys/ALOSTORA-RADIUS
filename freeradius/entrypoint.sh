#!/bin/sh
set -eu

: "${RADIUS_INTERNAL_API_KEY:?RADIUS_INTERNAL_API_KEY is required}"
RADIUS_API_URL="${RADIUS_API_URL:-http://api:8000/internal/radius/clients}"
tmp_json="$(mktemp)"
tmp_clients="/etc/raddb/clients.d/alostora.conf.tmp"
trap 'rm -f "$tmp_json" "$tmp_clients"' EXIT

attempt=0
until curl --silent --show-error --fail \
    -H "X-Radius-Internal-Key: $RADIUS_INTERNAL_API_KEY" \
    "$RADIUS_API_URL" --output "$tmp_json"; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "Could not fetch RADIUS NAS clients from the API after 30 attempts." >&2
        exit 1
    fi
    sleep 2
done

/usr/local/bin/alostora-generate-radius-clients < "$tmp_json" > "$tmp_clients"
chown freerad:freerad "$tmp_clients"
chmod 0600 "$tmp_clients"
mv "$tmp_clients" /etc/raddb/clients.d/alostora.conf
rm -f "$tmp_json"

freeradius -XC
exec "$@"
