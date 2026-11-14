FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl freeradius freeradius-rest python3 \
    && rm -rf /var/lib/apt/lists/*

COPY raddb/mods-available/rest /etc/freeradius/3.0/mods-available/rest
COPY raddb/sites-available/alostora.template /opt/alostora.template
COPY render_clients.py /usr/local/bin/render-radius-clients
COPY entrypoint.sh /usr/local/bin/alostora-radius-entrypoint

RUN chmod 0755 /usr/local/bin/render-radius-clients /usr/local/bin/alostora-radius-entrypoint \
    && ln -sf ../mods-available/rest /etc/freeradius/3.0/mods-enabled/rest \
    && rm -f /etc/freeradius/3.0/sites-enabled/default \
              /etc/freeradius/3.0/sites-enabled/inner-tunnel \
              /etc/freeradius/3.0/mods-enabled/eap \
    && sed 's|__RADIUS_INTERNAL_API_KEY__|build-validation-key-012345678901234567890123456789|g' \
       /opt/alostora.template > /etc/freeradius/3.0/sites-enabled/alostora \
    && freeradius -XC

EXPOSE 1812/udp 1813/udp

ENTRYPOINT ["/usr/local/bin/alostora-radius-entrypoint"]
