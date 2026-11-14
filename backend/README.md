# Backend

FastAPI service for ALOSTORA-RADIUS.

## Local container
Run from repository root:

```bash
docker compose up --build -d
```

- Health: http://localhost:8000/health
- OpenAPI docs: http://localhost:8000/docs

The initial endpoint is a process health check only. Database connectivity, migrations, authentication, and business modules will be implemented in subsequent stages.
