"""FastAPI entry point for the TeachIntent React web application."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import app_service
from .web_models import ExampleSummary, HealthResponse, WorkbenchResponse


def create_app() -> FastAPI:
    app = FastAPI(title="TeachIntent Web API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET"],
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

    return app


app = create_app()


__all__ = ["app", "create_app"]
