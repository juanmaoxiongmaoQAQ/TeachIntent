"""FastAPI entry point for the TeachIntent React web application."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import app_service
from .web_models import (
    EvaluateRequest,
    ExampleSummary,
    GenerateRequest,
    HealthResponse,
    LiveEvaluationResponse,
    LiveGenerationResponse,
    WorkbenchResponse,
)


def create_app() -> FastAPI:
    app = FastAPI(title="TeachIntent Web API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", application="TeachIntent")

    @app.get("/api/examples", response_model=list[ExampleSummary])
    def examples() -> list[ExampleSummary]:
        try:
            return app_service.list_examples()
        except app_service.AppServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/examples/{example_name}", response_model=WorkbenchResponse)
    def example(example_name: str, prompt_version: str = "v0.2") -> WorkbenchResponse:
        try:
            return app_service.build_recorded_workbench(
                example_name,
                prompt_version=prompt_version,
            )
        except app_service.ExampleNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except app_service.AppServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/generate", response_model=LiveGenerationResponse)
    def generate(request: GenerateRequest) -> LiveGenerationResponse:
        try:
            return app_service.generate_live_workbench(request)
        except app_service.LiveGenerationError as exc:
            status_code = 400 if exc.failure_type == "input_validation_error" else 502
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": {
                        "type": exc.failure_type,
                        "message": exc.summary,
                    }
                },
            ) from exc

    @app.post("/api/evaluate", response_model=LiveEvaluationResponse)
    def evaluate(request: EvaluateRequest) -> LiveEvaluationResponse:
        try:
            return app_service.evaluate_live_session(request.session_id)
        except app_service.LiveSessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "type": "unknown_session",
                        "message": app_service.sanitize_error_summary(exc),
                    }
                },
            ) from exc

    @app.get("/api/audio/{example_name}/{condition}")
    def audio(
        example_name: str,
        condition: Literal["neutral", "planned"],
    ) -> FileResponse:
        try:
            path = app_service.resolve_public_voice_audio_path(
                example_name,
                condition,
            )
        except app_service.ExampleNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except app_service.VoiceArtifactUnavailable as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(path, media_type="audio/wav", filename=path.name)

    return app


app = create_app()


__all__ = ["app", "create_app"]
