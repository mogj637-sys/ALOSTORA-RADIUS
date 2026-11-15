#!/usr/bin/env bash
set -euo pipefail

PROJECT="alostora-radius-e2e"
ENV_FILE=".env.e2e"

: "${RADIUS_SHARED_SECRET:?RADIUS_SHARED_SECRET must be set by the workflow}"
: "${RADIUS_INTERNAL_API_KEY:?RADIUS_INTERNAL_API_KEY must be set by the workflow}"

cat > "$ENV_FILE" <<EOF
POSTGRES_DB=$POSTGRES_DB
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DATABASE_URL=postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@db:5432/$POSTGRES_DB
APP_ENV=development
APP_SECRET_KEY=$APP_SECRET_KEY
JWT_ACCESS_TOKEN_MINUTES=30
CREDENTIAL_ENCRYPTION_KEY=$CREDENTIAL_ENCRYPTION_KEY
ROUTER_SECRET_ENCRYPTION_KEY=$ROUTER_SECRET_ENCRYPTION_KEY
RADIUS_INTERNAL_API_KEY=$RADIUS_INTERNAL_API_KEY
RADIUS_COA_ENABLED=false
RADIUS_COA_PORT=1700
RADIUS_COA_TIMEOUT_SECONDS=2
EOF

compose() {
  docker compose --env-file "$ENV_FILE" -p "$PROJECT" "$@"
}

compose up -d --build

# The API container runs migrations before becoming healthy.
for attempt in $(seq 1 60); do
  if compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "API did not become ready" >&2
    compose logs api
    exit 1
  fi
  sleep 2
done

compose exec -T -e RADIUS_SHARED_SECRET="$RADIUS_SHARED_SECRET" api python /app/scripts/radius_e2e.py seed
# FreeRADIUS creates its NAS clients file on startup, so reload after seeding the NAS.
compose restart freeradius
sleep 3

compose exec -T -e RADIUS_TEST_SHARED_SECRET="$RADIUS_SHARED_SECRET" freeradius sh -ec '
set -eu
NAS="alostora-e2e"
USER="E2E-RADIUS-USER"
PASSWORD="e2e-card-password-2026"
SERVER="127.0.0.1"

wrong_output="$(printf "User-Name = \"%s\"\nUser-Password = \"wrong-password\"\nNAS-Identifier = \"%s\"\nNAS-IP-Address = %s\n" "$USER" "$NAS" "$SERVER" | radclient -x -r 1 -t 3 "$SERVER:1812" auth "$RADIUS_TEST_SHARED_SECRET" 2>&1 || true)"
printf "%s\n" "$wrong_output"
printf "%s\n" "$wrong_output" | grep -q "Access-Reject"

CHALLENGE="0102030405060708"
CHAP_PASSWORD="$(python3 -c "import hashlib,sys; p=sys.argv[1].encode(); c=bytes.fromhex(sys.argv[2]); i=bytes([1]); print((i+hashlib.md5(i+p+c).digest()).hex())" "$PASSWORD" "$CHALLENGE")"
chap_output="$(printf "User-Name = \"%s\"\nCHAP-Password = 0x%s\nCHAP-Challenge = 0x%s\nNAS-Identifier = \"%s\"\nNAS-IP-Address = %s\n" "$USER" "$CHAP_PASSWORD" "$CHALLENGE" "$NAS" "$SERVER" | radclient -x -r 1 -t 3 "$SERVER:1812" auth "$RADIUS_TEST_SHARED_SECRET" 2>&1)"
printf "%s\n" "$chap_output"
printf "%s\n" "$chap_output" | grep -q "Access-Accept"

send_accounting() {
  printf "%s\n" "$1" | radclient -x -r 1 -t 3 "$SERVER:1813" acct "$RADIUS_TEST_SHARED_SECRET"
}
COMMON="User-Name = \"$USER\"\nNAS-Identifier = \"$NAS\"\nNAS-IP-Address = $SERVER\nAcct-Session-Id = \"alostora-e2e-session-001\"\nFramed-IP-Address = 10.10.0.10\nCalling-Station-Id = \"AA-BB-CC-DD-EE-FF\""
start_packet="$(printf "$COMMON\nAcct-Status-Type = Start\n")"
interim_packet="$(printf "$COMMON\nAcct-Status-Type = Interim-Update\nAcct-Session-Time = 30\nAcct-Input-Octets = 100\nAcct-Output-Octets = 200\n")"
stop_packet="$(printf "$COMMON\nAcct-Status-Type = Stop\nAcct-Session-Time = 30\nAcct-Input-Octets = 100\nAcct-Output-Octets = 200\n")"
send_accounting "$start_packet"
send_accounting "$interim_packet"
send_accounting "$stop_packet"
'

compose exec -T api python /app/scripts/radius_e2e.py verify
echo "FreeRADIUS UDP end-to-end integration passed."
