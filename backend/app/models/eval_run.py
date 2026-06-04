"""评测运行历史 ORM（Week 3）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class EvalRun(Base):
    """单次 run_rag_eval 运行摘要。"""

    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    dataset_version: Mapped[str] = mapped_column(String(16), default="v1")
    eval_mode: Mapped[str] = mapped_column(String(32), default="retrieval_only")
    ci_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sample_count: Mapped[int] = mapped_column(default=0)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_json: Mapped[str] = mapped_column(Text, nullable=False)

    samples: Mapped[list["EvalSampleResult"]] = relationship(
        "EvalSampleResult", back_populates="run", cascade="all, delete-orphan"
    )


class EvalSampleResult(Base):
    """单条样本评测结果（精简字段）。"""

    __tablename__ = "eval_sample_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True
    )
    sample_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_id: Mapped[str] = mapped_column(String(36), nullable=False)
    q_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[EvalRun] = relationship("EvalRun", back_populates="samples")
