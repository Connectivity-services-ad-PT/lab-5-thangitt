# Readiness Checklist - Lab 05

Checklist used before submitting the Docker Compose stack.

- [x] **Database ready:** `fit4110-db-lab05` is healthy and `pg_isready -U lab05 -d iotdb` returns accepting connections.
- [x] **AI service ready:** `fit4110-ai-lab05` is healthy, `GET /health` returns 200, and API calls `POST /predict` internally when creating readings.
- [x] **API ready:** `fit4110-api-lab05` is healthy, `GET /health` returns 200, and readings can be created/read with a valid bearer token.
- [x] **Environment variables:** runtime values are documented in `.env.example`; no real secrets are committed.
- [x] **Network & Ports:** `team-internal` is active; API reaches DB by hostname `db` and AI by hostname `ai-service`; host ports 8000 and 9000 are mapped.
- [x] **Image tags:** local images are built with `v0.1.0-team-iot` tags:
  `fit4110/iot-ingestion:v0.1.0-team-iot` and `fit4110/ai-service:v0.1.0-team-iot`.

Additional notes:

```text
- Newman compose test passed: 7 requests, 14 assertions, 0 failures.
- Reports generated:
  reports/newman-lab05-compose.xml
  reports/newman-lab05-compose.html
- Registry push is not performed here because Docker Hub/GHCR credentials are environment-specific.
```
