# Lab 05 Compose Health Evidence

Generated on 2026-06-15 after running:

```bash
docker compose up -d --build
npm run test:compose
```

## Container Status

```text
NAME                IMAGE                                   SERVICE      STATUS
fit4110-ai-lab05    fit4110/ai-service:v0.1.0-team-iot      ai-service   Up (healthy), port 9000
fit4110-api-lab05   fit4110/iot-ingestion:v0.1.0-team-iot   api          Up (healthy), port 8000
fit4110-db-lab05    postgres:15-alpine                      db           Up (healthy), port 5432 internal
```

## Health Checks

```json
{"status":"ok","service":"iot-ingestion","version":"0.5.0"}
{"status":"ok","service":"ai-service","version":"0.5.0"}
```

## Database Readiness

```text
/var/run/postgresql:5432 - accepting connections
```

## Image Tags

```text
fit4110/ai-service:v0.1.0-team-iot 9754b0585e41
fit4110/iot-ingestion:v0.1.0-team-iot 651ed9276c2b
```

## Newman Summary

```text
requests: 7 executed, 0 failed
assertions: 14 executed, 0 failed
reports/newman-lab05-compose.xml
reports/newman-lab05-compose.html
```
