FROM freeradius/freeradius-server:3.2.10

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl python3 \
    && rm -rf /var/lib/apt/lists/*

COPY clients.conf /etc/freeradius/3.0/clients.conf
COPY mods-available/rest /etc/freeradius/3.0/mods-available/rest
COPY sites-enabled/default /etc/freeradius/3.0/sites-enabled/default
COPY generate_clients.py /usr/local/bin/alostora-generate-radius-clients
COPY entrypoint.sh /usr/local/bin/alostora-radius-entrypoint

RUN chmod 0755 /usr/local/bin/alostora-generate-radius-clients /usr/local/bin/alostora-radius-entrypoint \
    && mkdir -p /etc/freeradius/3.0/clients.d \
    && ln -sf ../mods-available/rest /etc/freeradius/3.0/mods-enabled/rest \
    && ln -sf ../mods-available/json /etc/freeradius/3.0/mods-enabled/json \
    && chown -R freerad:freerad /etc/freeradius/3.0/clients.d

EXPOSE 1812/udp 1813/udp

ENTRYPOINT ["/usr/local/bin/alostora-radius-entrypoint"]
CMD ["freeradius", "-f"]
