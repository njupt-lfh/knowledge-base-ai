"""入库冲突与预检 API Schema。

定义冲突裁决、入库预检请求/响应的 Pydantic 模型，
由 `api/conflict.py`、`api/ingestion.py` 与对应服务使用。
"""

from pydantic import BaseModel, Field


class ConflictResolveRequest(BaseModel):
    """冲突裁决请求体。"""

    resolution: str = Field(
        ...,
        description="resolved_keep_new | resolved_keep_old | dismissed",
    )


class IngestPrecheckRequest(BaseModel):
    """入库前内容预检请求体。"""

    content: str = Field(..., min_length=1)


class IngestPrecheckResponse(BaseModel):
    """入库预检结果响应。"""

    status: str
    duplicate_of: str | None = None
    similarity: float | None = None
    llm_calls: int = 0
    message: str | None = None
