
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from entra_auth import (
    AuthenticatedUser,
    get_current_user,
)

from rag_pipeline import answer_question
from audit_logger import audit_event
from telemetry import configure_telemetry
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace

configure_telemetry_enabled = configure_telemetry()

app = FastAPI(
    title="Secure Enterprise RAG API",
    version="0.1.0",
    description=(
        "Enterprise RAG API protected by Microsoft Entra ID"
    ),
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    span = trace.get_current_span()

    if span.is_recording():
        span.set_attribute("rag.request_id", request_id)

    try:
        response = await call_next(request)
    except Exception:
        response = Response(
            content='{"detail":"Internal Server Error"}',
            status_code=500,
            media_type="application/json",
        )

    if response.status_code == 401:
        audit_event(
            "api.authentication.denied",
            request_id,
            "anonymous",
            "denied",
            reason="authentication_failed",
        )
    elif response.status_code >= 500:
        audit_event(
            "api.request.failed",
            request_id,
            "anonymous",
            "error",
            reason="server_error",
        )

    response.headers["X-Request-ID"] = request_id
    return response


class QueryRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )

    model_config = {
        "extra": "forbid",
    }


class QueryResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    http_request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        answer = answer_question(
            username=user.user_id,
            question=request.question,
            verified_groups=user.groups,
            request_id=http_request.state.request_id,
        )

        return QueryResponse(answer=answer)

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )


if configure_telemetry_enabled:
    FastAPIInstrumentor.instrument_app(
        app,
        http_capture_headers_server_request=[],
        http_capture_headers_server_response=[],
    )