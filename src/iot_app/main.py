import os
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Dict, List, Optional

import psycopg
import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "iot-ingestion")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
POSTGRES_USER = os.getenv("POSTGRES_USER", "lab05")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "lab05pass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "iotdb")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:9000")

app = FastAPI(
    title="FIT4110 Lab 05 - IoT Ingestion Service",
    version=SERVICE_VERSION,
    description="IoT Ingestion API for Lab 05 Docker Compose readiness.",
)


class SensorMetric(str, Enum):
    temperature = "temperature"
    humidity = "humidity"
    motion = "motion"
    smoke = "smoke"


class SensorUnit(str, Enum):
    celsius = "celsius"
    percent = "percent"
    boolean = "boolean"
    ppm = "ppm"


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class SensorReadingCreate(BaseModel):
    device_id: str = Field(..., min_length=3, examples=["ESP32-LAB-A01"])
    metric: SensorMetric = Field(..., examples=["temperature"])
    value: float = Field(
        ...,
        ge=-40,
        le=80,
        description="Boundary range used in Lab 03 and Lab 04: -40 to 80.",
        examples=[31.5],
    )
    unit: Optional[SensorUnit] = Field(default=None, examples=["celsius"])
    timestamp: str = Field(..., examples=["2026-05-13T08:30:00+07:00"])


class SensorReading(BaseModel):
    reading_id: str
    device_id: str
    metric: SensorMetric
    value: float
    unit: Optional[SensorUnit] = None
    timestamp: str
    created_at: str


class SensorReadingCreated(BaseModel):
    reading_id: str
    device_id: str
    metric: SensorMetric
    accepted: bool
    created_at: str


def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id BIGSERIAL PRIMARY KEY,
                reading_id TEXT UNIQUE NOT NULL,
                device_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                unit TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL,
                ai_objects TEXT,
                ai_confidence TEXT
            )
            """
        )


@app.on_event("startup")
def startup() -> None:
    init_db()


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=HTTPStatus(exc.status_code).phrase,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", HTTPStatus(exc.status_code).phrase)
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_reading_id(conn) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    row = conn.execute("SELECT COUNT(*) AS count FROM readings").fetchone()
    return f"R-{today}-{row['count'] + 1:04d}"


def check_ai_service() -> None:
    response = requests.get(f"{AI_SERVICE_URL}/health", timeout=3)
    response.raise_for_status()


def get_ai_prediction() -> Dict:
    response = requests.post(f"{AI_SERVICE_URL}/predict", timeout=3)
    response.raise_for_status()
    return response.json()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
        check_ai_service()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_problem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Service Unavailable",
                detail=f"Dependency readiness check failed: {exc}",
                instance="/health",
                problem_type="https://smart-campus.local/problems/dependency-unavailable",
            ),
        ) from exc

    return HealthResponse(status="ok", service=SERVICE_NAME, version=SERVICE_VERSION)


@app.post(
    "/readings",
    response_model=SensorReadingCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
        429: {"model": ProblemDetails},
        503: {"model": ProblemDetails},
    },
)
def create_reading(payload: SensorReadingCreate, response: Response) -> SensorReadingCreated:
    if payload.metric == SensorMetric.temperature and payload.value >= 70:
        response.headers["X-Warning"] = "high-temperature"

    try:
        prediction = get_ai_prediction()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_problem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Service Unavailable",
                detail=f"AI prediction failed: {exc}",
                instance="/readings",
                problem_type="https://smart-campus.local/problems/ai-unavailable",
            ),
        ) from exc

    created_at = now_iso()
    with get_db_connection() as conn:
        reading_id = next_reading_id(conn)
        conn.execute(
            """
            INSERT INTO readings (
                reading_id, device_id, metric, value, unit, timestamp, created_at,
                ai_objects, ai_confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                reading_id,
                payload.device_id,
                payload.metric.value,
                payload.value,
                payload.unit.value if payload.unit else None,
                payload.timestamp,
                created_at,
                ",".join(prediction.get("objects", [])),
                ",".join(str(item) for item in prediction.get("confidence", [])),
            ),
        )

    return SensorReadingCreated(
        reading_id=reading_id,
        device_id=payload.device_id,
        metric=payload.metric,
        accepted=True,
        created_at=created_at,
    )


@app.get("/readings/latest", dependencies=[Depends(verify_bearer_token)])
def latest_readings(
    device_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> Dict[str, List[Dict]]:
    query = """
        SELECT reading_id, device_id, metric, value, unit, timestamp, created_at
        FROM readings
    """
    params = []
    if device_id:
        query += " WHERE device_id = %s"
        params.append(device_id)
    query += " ORDER BY id DESC LIMIT %s"
    params.append(limit)

    with get_db_connection() as conn:
        items = conn.execute(query, params).fetchall()

    return {"items": list(reversed(items))}


@app.get("/readings/{reading_id}", dependencies=[Depends(verify_bearer_token)])
def get_reading(reading_id: str) -> Dict:
    with get_db_connection() as conn:
        item = conn.execute(
            """
            SELECT reading_id, device_id, metric, value, unit, timestamp, created_at
            FROM readings
            WHERE reading_id = %s
            """,
            (reading_id,),
        ).fetchone()

    if item:
        return item

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=build_problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=f"Reading {reading_id} does not exist",
            instance=f"/readings/{reading_id}",
            problem_type="https://smart-campus.local/problems/not-found",
        ),
    )
