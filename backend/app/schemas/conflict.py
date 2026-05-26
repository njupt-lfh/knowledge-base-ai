from pydantic import BaseModel, Field


class ConflictResolveRequest(BaseModel):
    resolution: str = Field(
        ...,
        description="resolved_keep_new | resolved_keep_old | dismissed",
    )


class IngestPrecheckRequest(BaseModel):
    content: str = Field(..., min_length=1)


class IngestPrecheckResponse(BaseModel):
    status: str
    duplicate_of: str | None = None
    similarity: float | None = None
    llm_calls: int = 0
    message: str | None = None
