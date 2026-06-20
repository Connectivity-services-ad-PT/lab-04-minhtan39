import os
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


SERVICE_NAME = os.getenv("SERVICE_NAME", "camera-stream")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.4.0-team-camera")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "http://localhost:4011")
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://localhost:4012")
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "3.0"))

app = FastAPI(
    title="FIT4110 Lab 04 - Camera Stream Service",
    version=SERVICE_VERSION,
    description="Dockerized Camera Stream API for Smart Campus team-camera.",
)


class FrameFormat(str, Enum):
    jpeg = "jpeg"
    png = "png"


class MotionLevel(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


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
    dependencies: Dict[str, str]


class FrameCreate(BaseModel):
    camera_id: str = Field(..., min_length=3, examples=["CAM-A01"])
    location: str = Field(..., min_length=2, examples=["Main lobby"])
    frame_format: FrameFormat = Field(default=FrameFormat.jpeg)
    image_base64: str = Field(..., min_length=16, max_length=500000)
    captured_at: str = Field(..., examples=["2026-05-13T08:30:00+07:00"])
    motion_score: float = Field(..., ge=0, le=1, examples=[0.82])


class FrameAccepted(BaseModel):
    frame_id: str
    camera_id: str
    accepted: bool
    motion_level: MotionLevel
    created_at: str


class AnalyzeRequest(BaseModel):
    frame_id: str = Field(..., examples=["FR-20260513-0001"])


FRAMES: List[Dict] = []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_frame_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"FR-{today}-{len(FRAMES) + 1:04d}"


def motion_level(score: float) -> MotionLevel:
    if score >= 0.75:
        return MotionLevel.high
    if score >= 0.4:
        return MotionLevel.medium
    if score > 0:
        return MotionLevel.low
    return MotionLevel.none


def build_vision_payload(frame_id: str, frame: Dict) -> Dict:
    return {
        "request_id": f"vision-{frame_id}",
        "camera_id": frame["camera_id"],
        "timestamp": frame["captured_at"],
        "location": frame["location"],
        "motion_score": frame["motion_score"],
        "image_base64": frame["image_base64"],
        "snapshot_url": None,
    }


def build_camera_event(frame_id: str, frame: Dict, vision_body: Dict) -> Dict:
    risk_level = vision_body.get("risk_level", "low") if isinstance(vision_body, dict) else "low"
    unknown_person = bool(vision_body.get("unknown_person", False)) if isinstance(vision_body, dict) else False
    return {
        "event_type": "camera.motion.analyzed",
        "source_service": "team-camera",
        "request_id": f"vision-{frame_id}",
        "frame_id": frame_id,
        "camera_id": frame["camera_id"],
        "location": frame["location"],
        "occurred_at": now_iso(),
        "timestamp": frame["captured_at"],
        "motion_detected": True,
        "motion_score": frame["motion_score"],
        "motion_level": frame["motion_level"],
        "risk_level": risk_level,
        "unknown_person": unknown_person,
        "alert_candidate": risk_level in {"high", "critical"} or unknown_person,
    }


def build_problem(status_code: int, title: str, detail: str, instance: Optional[str] = None) -> Dict:
    return {
        "type": f"https://smart-campus.local/problems/{title.lower().replace(' ', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    problem = exc.detail if isinstance(exc.detail, dict) else build_problem(
        exc.status_code,
        status.HTTP_STATUS_CODES.get(exc.status_code, "HTTP Error"),
        str(exc.detail),
        str(request.url.path),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    detail = f"{'.'.join(str(x) for x in first_error.get('loc', []))}: {first_error.get('msg', 'invalid request')}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(422, "Validation error", detail, str(request.url.path)),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(401, "Unauthorized", "Missing or invalid bearer token"),
        )


async def post_with_timeout(url: str, payload: Dict) -> Dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return {"ok": True, "status": response.status, "body": json.loads(body) if body else {}}
    except TimeoutError:
        raise HTTPException(503, build_problem(503, "Dependency timeout", f"Timeout calling {url}"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, build_problem(502, "Dependency error", f"{url} returned {exc.code}"))
    except urllib.error.URLError as exc:
        raise HTTPException(503, build_problem(503, "Dependency unavailable", f"Cannot connect to {url}: {exc.reason}"))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        dependencies={"vision": VISION_SERVICE_URL, "analytics": ANALYTICS_URL},
    )


@app.post("/api/v1/frames", response_model=FrameAccepted, status_code=201, dependencies=[Depends(verify_bearer_token)])
async def upload_frame(payload: FrameCreate) -> FrameAccepted:
    frame_id = next_frame_id()
    created_at = now_iso()
    item = payload.model_dump()
    item.update({"frame_id": frame_id, "created_at": created_at, "motion_level": motion_level(payload.motion_score).value})
    FRAMES.append(item)
    return FrameAccepted(frame_id=frame_id, camera_id=payload.camera_id, accepted=True, motion_level=item["motion_level"], created_at=created_at)


@app.post("/api/v1/frames/{frame_id}/analyze", dependencies=[Depends(verify_bearer_token)])
async def analyze_frame(frame_id: str) -> Dict:
    frame = next((item for item in FRAMES if item["frame_id"] == frame_id), None)
    if frame is None:
        raise HTTPException(404, build_problem(404, "Not found", f"Frame {frame_id} does not exist"))

    vision_payload = build_vision_payload(frame_id, frame)
    vision_result = await post_with_timeout(
        f"{VISION_SERVICE_URL.rstrip('/')}/api/v1/detect",
        vision_payload,
    )
    vision_body = vision_result.get("body", {}) if isinstance(vision_result, dict) else {}
    analytics_event = build_camera_event(frame_id, frame, vision_body)
    analytics_result = await post_with_timeout(
        f"{ANALYTICS_URL.rstrip('/')}/api/v1/events",
        analytics_event,
    )
    return {
        "frame_id": frame_id,
        "vision_request": vision_payload,
        "vision": vision_body or vision_result,
        "analytics_event": analytics_event,
        "analytics": analytics_result,
    }


@app.get("/api/v1/frames", dependencies=[Depends(verify_bearer_token)])
def list_frames(camera_id: Optional[str] = Query(default=None), limit: int = Query(default=20, ge=1, le=100)) -> Dict:
    items = FRAMES
    if camera_id:
        items = [item for item in items if item["camera_id"] == camera_id]
    return {"items": items[-limit:]}


@app.get("/api/v1/frames/{frame_id}", dependencies=[Depends(verify_bearer_token)])
def get_frame(frame_id: str) -> Dict:
    frame = next((item for item in FRAMES if item["frame_id"] == frame_id), None)
    if frame is None:
        raise HTTPException(404, build_problem(404, "Not found", f"Frame {frame_id} does not exist"))
    return frame
