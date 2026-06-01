"""知识库治理 API 请求 Schema。

定义批量治理动作与扫描选项的 Pydantic 模型，
由 `api/governance.py` 与 `GovernanceService` 使用。
"""

from pydantic import BaseModel, Field


class GovernanceActionRequest(BaseModel):
    """执行治理动作请求体。"""

    action: str = Field(..., description="archive | deactivate | boost_faq | merge")
    chunk_ids: list[str] = Field(..., min_length=1)


class GovernanceScanQuery(BaseModel):
    """治理扫描查询参数（可选 body/query 封装）。"""

    scan_duplicates: bool = True
