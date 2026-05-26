from pydantic import BaseModel, Field


class GovernanceActionRequest(BaseModel):
    action: str = Field(..., description="archive | deactivate | boost_faq | merge")
    chunk_ids: list[str] = Field(..., min_length=1)


class GovernanceScanQuery(BaseModel):
    scan_duplicates: bool = True
