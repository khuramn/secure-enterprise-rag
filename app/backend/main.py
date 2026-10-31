import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion" / "src"))
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .auth import Forbidden, Settings, TokenValidator
from audit_logger import audit_event


@asynccontextmanager
async def lifespan(app):
    app.state.validator = TokenValidator(Settings.from_env())
    yield


app = FastAPI(lifespan=lifespan, debug=False)
bearer = HTTPBearer(auto_error=False)


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=8000, strict=True)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value


class Answer(BaseModel):
    answer: str
    request_id: str


def authenticate(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return request.app.state.validator.validate(credentials.credentials)
    except Forbidden:
        audit_event("api.authorization.denied", str(uuid4()), "unresolved", "denied", reason="claims_policy")
        raise HTTPException(403, "Access denied") from None
    except (jwt.PyJWTError, ValueError, TypeError):
        audit_event("api.authentication.denied", str(uuid4()), "unresolved", "denied", reason="invalid_token")
        raise HTTPException(401, "Invalid access token", headers={"WWW-Authenticate": "Bearer"}) from None


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Service unavailable"})


# FastAPI's default validation response echoes rejected input. Omit it.
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=Answer)
def query(body: Query, identity=Depends(authenticate)):
    request_id = str(uuid4())
    try:
        from rag_pipeline import answer_question
        answer = answer_question(identity, body.question)
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Empty answer")
        return Answer(answer=answer, request_id=request_id)
    except Exception:
        audit_event("api.query.failed", request_id, identity.audit_subject, "error", reason="pipeline_failure")
        # Do not expose or log SDK exceptions, prompts, or retrieved content.
        raise HTTPException(503, "Service unavailable") from None
