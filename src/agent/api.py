"""Thin FastAPI/SSE transport for an injected ``AgentService``."""

from __future__ import annotations

import json
from typing import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from .schemas import AgentEvent, AgentRequest, AgentRunResult
from .service import AgentService


def _sse(event: AgentEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return "event: {}\ndata: {}\n\n".format(event.event, payload)


def create_app(agent_service: AgentService) -> FastAPI:
    """Create the API without constructing a model or touching the network."""

    if agent_service is None:
        raise ValueError("agent_service is required")
    app = FastAPI(title="Co-Work Agent API", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        return agent_service.health()

    @app.post("/api/agent/chat", response_model=AgentRunResult)
    def chat(request: AgentRequest) -> AgentRunResult:
        return agent_service.run(request)

    @app.post("/api/agent/chat/stream")
    def chat_stream(request: AgentRequest) -> StreamingResponse:
        def events() -> Iterator[str]:
            for event in agent_service.stream(request):
                yield _sse(event)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


__all__ = ["create_app"]
