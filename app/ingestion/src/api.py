
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from entra_auth import (
    AuthenticatedUser,
    get_current_user,
)
from rag_pipeline import answer_question


app = FastAPI(
    title="Secure Enterprise RAG API",
    version="0.1.0",
    description=(
        "Enterprise RAG API protected by Microsoft Entra ID"
    ),
)


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
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        answer = answer_question(
            username=user.user_id,
            question=request.question,
            verified_groups=user.groups,
        )

        return QueryResponse(answer=answer)

    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )
