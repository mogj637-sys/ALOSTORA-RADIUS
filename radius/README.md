# ALOSTORA FreeRADIUS service

This container runs FreeRADIUS 3 with the REST module.

## Runtime behavior

- Listens for authentication on UDP 1812 and accounting on UDP 1813.
- Loads active NAS clients from the protected Backend endpoint at startup.
- Uses the router's configured RADIUS client IP/CIDR and decrypted shared secret to generate `clients.conf`.
- Sends authentication and accounting requests to the internal FastAPI RADIUS endpoints.
- Uses `RADIUS_INTERNAL_API_KEY` for the private API header.

When a router is added or its RADIUS client address/shared secret changes, restart the service so it reloads the client list:

```sh
docker compose restart radius
```

A router must have a RADIUS client IP/CIDR configured, and its NAS-Identifier must match the registered NAS Identifier. The management/API address is not automatically assumed to be the RADIUS packet source address.

This is an initial REST-backed integration. CoA/Disconnect, live client-list refresh without restart, and a real MikroTik end-to-end test remain future work.
