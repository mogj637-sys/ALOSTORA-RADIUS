#!/bin/sh
set -eu

: "${RADIUS_INTERNAL_API_KEY:?RADIUS_INTERNAL_API_KEY is required}"

CLIENTS_JSON=/tmp/alostora-radius-clients.json
CLIENTS_URL=http://api:8000/internal/radius/clients
attempt=0

until curl --fail --silent --show-error \
    -H "X-Radius-Internal-Key: ${RADIUS_INTERNAL_API_KEY}" \
    "${CLIENTS_URL}" -o "${CLIENTS_JSON}"; do
    attempt=$((attempt + 1))
    if [ "${attempt}" -ge 60 ]; then
        echo "Unable to load RADIUS clients from the API after 60 attempts." >&2
        exit 1
    fi
    sleep 2
done

/usr/local/bin/render-radius-clients "${CLIENTS_JSON}" > /etc/freeradius/3.0/clients.conf
sed "s|__RADIUS_INTERNAL_API_KEY__|${RADIUS_INTERNAL_API_KEY}|g" \
    /opt/alostora.template > /etc/freeradius/3.0/sites-enabled/alostora

exec freeradius -f -l stdout
