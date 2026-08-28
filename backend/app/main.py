import os
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from .capability_registry import conversation_and_imaging_tools
from .config import get_settings
from .images import ImagePredictionService, InvalidMedicalImage
from .orchestrator import TriageOrchestrator
from .predictions import InvalidAssessment, ModelUnavailable, PredictionService
from .qwen_runtime import AwsLambdaModelRunner, DockerModelRunner
from .rate_limit import RateLimitMiddleware
from .reports import build_pdf, build_xlsx
from .routing import HybridRouter, QwenJsonRouter, QwenSymptomQuestionSelector, RulesRouter
from .schemas import (
    PredictionRequest,
    PredictionResult,
    ReportExportRequest,
    TriageMessageRequest,
    TriageResponse,
    TriageStartRequest,
)
from .security import TokenCodec, TokenError
from .tool_registry import SpecialistToolRegistry
from .voice import InvalidAudio, MoonshineTranscriber, VoiceUnavailable

settings = get_settings()
codec = TokenCodec(settings.state_secret)
predictions = PredictionService(settings.artifacts_dir)
tool_registry = SpecialistToolRegistry(settings.artifacts_dir)
qwen_runtime = (
    AwsLambdaModelRunner(settings.qwen_lambda_function, settings.qwen_model)
    if settings.qwen_lambda_function
    else DockerModelRunner(settings.qwen_base_url, settings.qwen_model, settings.qwen_timeout_seconds)
)
rules_router = RulesRouter(tool_registry)
qwen_router = QwenJsonRouter(qwen_runtime)
active_router = (
    rules_router
    if settings.orchestrator_backend == "rules"
    else HybridRouter(qwen_router, rules_router, QwenSymptomQuestionSelector(qwen_runtime))
)
orchestrator = TriageOrchestrator(
    codec,
    registry=tool_registry,
    router=active_router,
    state_ttl_seconds=settings.triage_ttl_seconds,
)
transcriber = MoonshineTranscriber(settings)
image_predictions = ImagePredictionService(settings.artifacts_dir)

app = FastAPI(
    title="HealthAI Agent Lab API",
    version="0.1.0",
    description="Evaluation-driven educational screening APIs. Not a medical device.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials="*" not in settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
app.add_middleware(
    RateLimitMiddleware,
    secret=settings.state_secret,
    table_name=settings.quota_table,
    enabled=settings.rate_limit_enabled,
    secure_cookie=settings.environment == "production",
)


@app.get("/health")
def health():
    qwen = qwen_runtime.status() if settings.orchestrator_backend != "rules" else None
    active_backend = (
        "rules" if settings.orchestrator_backend == "rules" else "qwen" if qwen and qwen.available else "rules-fallback"
    )
    return {
        "status": "healthy",
        "service": "HealthAI Agent Lab",
        "environment": settings.environment,
        "voice_available": settings.voice_enabled or transcriber.available,
        "qwen_available": bool(qwen and qwen.available),
        "orchestrator_backend": active_backend,
    }


@app.get("/api/v1/models")
def models():
    return {"models": predictions.catalog()}


@app.get("/api/v1/tools")
def tools():
    qwen = qwen_runtime.status() if settings.orchestrator_backend != "rules" else None
    active_backend = (
        "rules" if settings.orchestrator_backend == "rules" else "qwen" if qwen and qwen.available else "rules-fallback"
    )
    return {
        "tools": [
            *[item.model_dump() for item in tool_registry.catalog()],
            *[item.model_dump() for item in conversation_and_imaging_tools(settings.artifacts_dir)],
        ],
        "orchestrator": {
            "active_backend": active_backend,
            "qwen_status": qwen.detail if qwen else "disabled",
            "policy_validation": "enforced",
            "emergency_gate": "deterministic-pre-routing",
        },
    }


@app.post("/api/v1/triage/start", response_model=TriageResponse)
def triage_start(request: TriageStartRequest):
    return orchestrator.start(request.message, request.locale)


@app.post("/api/v1/triage/message", response_model=TriageResponse)
def triage_message(request: TriageMessageRequest):
    try:
        return orchestrator.continue_session(request.state_token, request.message, request.locale)
    except TokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/assessments/{condition}/predict", response_model=PredictionResult)
def predict(condition: str, request: PredictionRequest):
    try:
        result = predictions.predict(condition, request.inputs)
    except InvalidAssessment as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    report_token = codec.encode({"kind": "report", "report": result}, ttl_seconds=1800)
    return PredictionResult(**result, report_token=report_token)


def _report_payload(request: ReportExportRequest) -> dict:
    try:
        return codec.decode(request.report_token, "report")["report"]
    except (TokenError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/reports/pdf")
def report_pdf(request: ReportExportRequest):
    payload = build_pdf(_report_payload(request), request.alias)
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=healthai-report.pdf"},
    )


@app.post("/api/v1/reports/xlsx")
def report_xlsx(request: ReportExportRequest):
    payload = build_xlsx(_report_payload(request), request.alias)
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=healthai-report.xlsx"},
    )


@app.post("/api/v1/voice/transcribe")
async def transcribe_voice(audio: Annotated[UploadFile, File()]):
    allowed = {"audio/wav": ".wav", "audio/x-wav": ".wav"}
    suffix = allowed.get(audio.content_type or "")
    if suffix is None:
        raise HTTPException(status_code=415, detail="Use 16 kHz mono WAV audio.")
    content = await audio.read(settings.max_audio_bytes + 1)
    try:
        transcript = transcriber.transcribe(content)
    except InvalidAudio as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "transcript": transcript,
        "requires_confirmation": True,
        "model": "HealthAI Voice 1.0",
        "model_release": "healthai-voice-v1.0.0",
        "base_model": "Moonshine Tiny Streaming English 34M",
    }


@app.post("/api/v1/images/pneumonia/predict", response_model=PredictionResult)
async def predict_pneumonia_image(image: Annotated[UploadFile, File()]):
    if image.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG or PNG chest X-ray image.")
    content = await image.read(settings.max_image_bytes + 1)
    if len(content) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="The image exceeds the 8 MB limit.")
    try:
        result = image_predictions.predict_pneumonia(content)
    except InvalidMedicalImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    report_token = codec.encode({"kind": "report", "report": result}, ttl_seconds=1800)
    return PredictionResult(**result, report_token=report_token)


frontend_dir = Path(os.environ.get("HEALTHAI_FRONTEND_DIR", "/var/task/frontend"))
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


handler = Mangum(app, lifespan="off")
