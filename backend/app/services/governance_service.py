"""冷知识治理服务（Phase 1.3）。

职责：
    扫描冷知识、低质量、重复 chunk 等，生成治理建议，
    并支持归档/禁用/FAQ 加权等批量操作。

在流水线中的位置：
    API governance 路由 → GovernanceService

依赖服务：
    - stats_service.cold_knowledge_count
    - ChunkService、QualityService、EmbeddingService
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.chroma_client import get_collection
from ..models.chunk import Chunk
from ..models.chunk_quality import ChunkQuality
from ..models.governance_suggestion import (
    GovernanceAuditLog,
    GovernanceSuggestion,
)
from ..services.chunk_service import ChunkService
from ..services.embedding_service import EmbeddingService
from ..services.quality_service import QualityService
from ..services.stats_service import cold_knowledge_count

logger = logging.getLogger(__name__)

COLD_DAYS = 90
DUPLICATE_SCAN_LIMIT = 40
# 归一化向量下 L2 距离 < 0.4 约等于余弦相似度 > 0.92
DUPLICATE_MAX_DISTANCE = 0.4

SUGGESTION_TYPES = (
    "duplicate",
    "cold_stale",
    "high_quality_zero_hit",
    "low_quality",
    "archive_candidate",
)

ACTION_ARCHIVE = "archive"
ACTION_DEACTIVATE = "deactivate"
ACTION_BOOST_FAQ = "boost_faq"


class GovernanceService:
    """知识库治理扫描与建议执行。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embed_svc = EmbeddingService()

    async def scan_suggestions(self, kb_id: str, *, scan_duplicates: bool = True) -> dict[str, Any]:
        """全量扫描并返回治理建议列表。

        参数:
            kb_id: 知识库 ID
            scan_duplicates: 是否执行向量重复扫描

        返回:
            含 health 摘要与 suggestions 的字典
        """
        suggestions: list[dict[str, Any]] = []
        suggestions.extend(await self._scan_cold_stale(kb_id))
        suggestions.extend(await self._scan_quality_issues(kb_id))
        if scan_duplicates:
            suggestions.extend(await self._scan_duplicates(kb_id))

        cold = await cold_knowledge_count(self.db, kb_id, COLD_DAYS)
        total = (
            await self.db.execute(
                select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == kb_id)
            )
        ).scalar() or 0
        active = (
            await self.db.execute(
                select(func.count(Chunk.id)).where(
                    Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True)
                )
            )
        ).scalar() or 0

        return {
            "kb_id": kb_id,
            "scanned_at": datetime.utcnow().isoformat(),
            "health": {
                **cold,
                "total_chunks": int(total),
                "active_chunks": int(active),
                "suggestions_count": len(suggestions),
            },
            "suggestions": suggestions,
        }

    async def _scan_cold_stale(self, kb_id: str) -> list[dict]:
        """扫描长期零命中的冷知识块。

        参数:
            kb_id: 知识库 ID

        返回:
            建议 dict 列表
        """
        cutoff = datetime.utcnow() - timedelta(days=COLD_DAYS)
        rows = (
            (
                await self.db.execute(
                    select(Chunk)
                    .where(
                        Chunk.knowledge_base_id == kb_id,
                        Chunk.is_active.is_(True),
                        Chunk.hit_count == 0,
                        Chunk.created_at <= cutoff,
                    )
                    .order_by(Chunk.created_at)
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        out: list[dict] = []
        for c in rows:
            out.append(
                _suggestion(
                    stype="cold_stale",
                    title=f"冷知识块 #{c.chunk_index}",
                    description=f"创建超过 {COLD_DAYS} 天且从未被命中，建议复审或归档。",
                    chunk_ids=[c.id],
                    action=ACTION_ARCHIVE,
                    severity="warning",
                    preview=c.content[:120],
                )
            )
        return out

    async def _scan_quality_issues(self, kb_id: str) -> list[dict]:
        """扫描低质量、高质量零命中、归档候选。

        参数:
            kb_id: 知识库 ID

        返回:
            建议 dict 列表
        """
        out: list[dict] = []
        q_rows = (
            await self.db.execute(
                select(ChunkQuality, Chunk)
                .join(Chunk, Chunk.id == ChunkQuality.chunk_id)
                .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
            )
        ).all()

        for q, chunk in q_rows:
            if q.needs_review and (chunk.hit_count or 0) > 0:
                out.append(
                    _suggestion(
                        stype="low_quality",
                        title=f"低质量待复审 #{chunk.chunk_index}",
                        description=f"质量分 {q.quality_score}，点踩 {q.dislike_count} 次。",
                        chunk_ids=[chunk.id],
                        action=ACTION_DEACTIVATE,
                        severity="error",
                        preview=chunk.content[:120],
                    )
                )
            elif q.quality_score >= 0.65 and (chunk.hit_count or 0) == 0:
                out.append(
                    _suggestion(
                        stype="high_quality_zero_hit",
                        title=f"高质量零命中 #{chunk.chunk_index}",
                        description="内容质量较好但从未被检索命中，可生成 FAQ 摘要提升曝光。",
                        chunk_ids=[chunk.id],
                        action=ACTION_BOOST_FAQ,
                        severity="info",
                        preview=chunk.content[:120],
                    )
                )
            elif q.quality_score < 0.25 and (chunk.hit_count or 0) == 0:
                out.append(
                    _suggestion(
                        stype="archive_candidate",
                        title=f"建议归档 #{chunk.chunk_index}",
                        description="低质量且零命中，可能为无用内容。",
                        chunk_ids=[chunk.id],
                        action=ACTION_ARCHIVE,
                        severity="warning",
                        preview=chunk.content[:120],
                    )
                )
        return out

    async def _scan_duplicates(self, kb_id: str) -> list[dict]:
        """向量近邻扫描疑似重复 chunk。

        参数:
            kb_id: 知识库 ID

        返回:
            重复建议 dict 列表
        """
        rows = (
            (
                await self.db.execute(
                    select(Chunk)
                    .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
                    .order_by(Chunk.created_at.desc())
                    .limit(DUPLICATE_SCAN_LIMIT)
                )
            )
            .scalars()
            .all()
        )

        out: list[dict] = []
        seen_pairs: set[frozenset[str]] = set()

        try:
            collection = get_collection(kb_id)
        except Exception:
            return out

        for chunk in rows:
            try:
                emb = self.embed_svc.embed_query(chunk.content[:2000])
                results = collection.query(
                    query_embeddings=[emb],
                    n_results=3,
                    include=["distances", "documents", "metadatas"],
                )
            except Exception:
                continue

            if not results or not results.get("ids") or not results["ids"][0]:
                continue

            for i, other_id in enumerate(results["ids"][0]):
                if other_id == chunk.id:
                    continue
                dist = results["distances"][0][i] if results.get("distances") else 1.0
                if dist > DUPLICATE_MAX_DISTANCE:
                    continue
                pair = frozenset({chunk.id, other_id})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                other_doc = results["documents"][0][i][:80] if results.get("documents") else ""
                sim = round(max(0.0, 1.0 - dist), 4)
                out.append(
                    _suggestion(
                        stype="duplicate",
                        title="疑似重复知识块",
                        description=f"与块 {other_id[:8]}… 高度相似（距离 {dist:.3f}，约 {sim}）。建议合并。",
                        chunk_ids=[chunk.id, other_id],
                        action="merge",
                        severity="warning",
                        preview=f"{chunk.content[:60]} … / {other_doc}",
                    )
                )
                break
        return out

    async def apply_action(self, kb_id: str, action: str, chunk_ids: list[str]) -> dict[str, Any]:
        """执行治理建议动作。

        参数:
            kb_id: 知识库 ID
            action: archive | deactivate | boost_faq | merge
            chunk_ids: 目标 chunk ID 列表

        返回:
            执行结果摘要

        Raises:
            ValueError: chunk_ids 为空或未知 action
        """
        if not chunk_ids:
            raise ValueError("chunk_ids required")

        chunk_svc = ChunkService(self.db)
        quality_svc = QualityService(self.db)
        applied = 0
        details: list[str] = []

        for cid in chunk_ids:
            chunk = await self.db.get(Chunk, cid)
            if not chunk or chunk.knowledge_base_id != kb_id:
                continue

            if action in (ACTION_ARCHIVE, ACTION_DEACTIVATE):
                if chunk.is_active:
                    await chunk_svc.toggle_status(cid, False)
                    applied += 1
                    details.append(f"{cid}: 已禁用/归档")
            elif action == ACTION_BOOST_FAQ:
                q = await quality_svc.get_or_create(cid)
                q.quality_score = min(1.0, (q.quality_score or 0.5) + 0.15)
                q.needs_review = False
                await self.db.commit()
                applied += 1
                details.append(f"{cid}: 质量分提升至 {q.quality_score}")
            elif action == "merge":
                details.append(f"{cid}: 合并需人工处理，请在知识块列表中编辑后禁用重复项")
            else:
                raise ValueError(f"unknown action: {action}")

        return {"action": action, "applied": applied, "details": details}

    # ── Phase 3 治理闭环：持久化 + 状态机 + 审计 + Chroma/FTS 同步 ──

    async def persist_suggestions(
        self,
        kb_id: str,
        suggestions: list[dict],
        *,
        scan_id: str = "",
    ) -> int:
        """将扫描结果持久化到 governance_suggestions 表（去重：同 type+chunk_ids 的 pending 跳过）。

        参数:
            kb_id: 知识库 ID
            suggestions: scan_suggestions 的输出
            scan_id: 本次扫描 ID

        返回:
            新写入条数
        """
        count = 0
        for s in suggestions:
            cids = s.get("chunk_ids", [])
            cids_json = json.dumps(sorted(cids))
            existing = await self.db.execute(
                select(GovernanceSuggestion).where(
                    GovernanceSuggestion.kb_id == kb_id,
                    GovernanceSuggestion.suggestion_type == s["type"],
                    GovernanceSuggestion.chunk_ids == cids_json,
                    GovernanceSuggestion.status == "pending",
                )
            )
            if existing.first():
                continue
            row = GovernanceSuggestion(
                kb_id=kb_id,
                suggestion_type=s["type"],
                title=s.get("title", ""),
                description=s.get("description", ""),
                chunk_ids=cids_json,
                recommended_action=s.get("recommended_action", ""),
                severity=s.get("severity", "warning"),
                status="pending",
                scan_id=scan_id or None,
                content_preview=s.get("content_preview", ""),
            )
            self.db.add(row)
            count += 1
        if count > 0:
            await self.db.commit()
        return count

    def _suggestion_filters(
        self,
        kb_id: str,
        *,
        status: str | None = None,
        suggestion_type: str | None = None,
    ) -> list:
        filters = [GovernanceSuggestion.kb_id == kb_id]
        if status:
            filters.append(GovernanceSuggestion.status == status)
        if suggestion_type:
            filters.append(GovernanceSuggestion.suggestion_type == suggestion_type)
        return filters

    async def list_suggestions(
        self,
        kb_id: str,
        *,
        status: str | None = None,
        suggestion_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """列出治理建议（分页 + 总数）。

        参数:
            kb_id: 知识库 ID
            status: 状态过滤
            suggestion_type: 类型过滤
            offset: 偏移量
            limit: 每页条数

        返回:
            {"items": GovernanceSuggestion 列表, "total": 符合条件的总数}
        """
        filters = self._suggestion_filters(kb_id, status=status, suggestion_type=suggestion_type)
        total = await self.db.scalar(select(func.count(GovernanceSuggestion.id)).where(*filters))
        q = (
            select(GovernanceSuggestion)
            .where(*filters)
            .order_by(GovernanceSuggestion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        return {"items": list(result.scalars().all()), "total": int(total or 0)}

    async def suggestion_status_counts(self, kb_id: str) -> dict[str, int]:
        """按状态统计治理建议数量（用于 Tab 角标，不受分页 limit 影响）。"""
        result = await self.db.execute(
            select(GovernanceSuggestion.status, func.count(GovernanceSuggestion.id))
            .where(GovernanceSuggestion.kb_id == kb_id)
            .group_by(GovernanceSuggestion.status)
        )
        counts = dict.fromkeys(("pending", "approved", "dismissed", "executed", "verified"), 0)
        for status, n in result.all():
            counts[str(status)] = int(n)
        return counts

    async def _write_audit(
        self,
        kb_id: str,
        suggestion_id: str,
        action: str,
        *,
        operator: str = "",
        chunk_ids: str = "",
        detail: str = "",
    ) -> None:
        """写入治理审计日志。"""
        self.db.add(
            GovernanceAuditLog(
                kb_id=kb_id,
                suggestion_id=suggestion_id,
                action=action,
                operator=operator or None,
                chunk_ids=chunk_ids or None,
                detail=detail or None,
            )
        )
        await self.db.commit()

    async def approve_suggestion(
        self,
        suggestion_id: str,
        *,
        operator: str = "",
    ) -> GovernanceSuggestion | None:
        """批准治理建议（pending → approved）。"""
        row = await self.db.get(GovernanceSuggestion, suggestion_id)
        if not row or row.status != "pending":
            return None
        row.status = "approved"
        row.approved_by = operator or None
        row.approved_at = datetime.utcnow()
        await self.db.commit()
        await self._write_audit(
            row.kb_id,
            suggestion_id,
            "approved",
            operator=operator,
            chunk_ids=row.chunk_ids,
            detail=f"批准治理建议: {row.title}",
        )
        return row

    async def dismiss_suggestion(
        self,
        suggestion_id: str,
        *,
        operator: str = "",
        reason: str = "",
    ) -> GovernanceSuggestion | None:
        """驳回治理建议（pending → dismissed）。"""
        row = await self.db.get(GovernanceSuggestion, suggestion_id)
        if not row or row.status != "pending":
            return None
        row.status = "dismissed"
        await self.db.commit()
        await self._write_audit(
            row.kb_id,
            suggestion_id,
            "dismissed",
            operator=operator,
            chunk_ids=row.chunk_ids,
            detail=f"驳回治理建议: {row.title}" + (f"，原因: {reason}" if reason else ""),
        )
        return row

    async def execute_suggestion(
        self,
        suggestion_id: str,
        *,
        operator: str = "",
    ) -> dict | None:
        """执行已批准的治理建议（approved → executed），同步 Chroma/FTS。

        返回执行结果 dict 或 None（状态不允许）。
        """
        row = await self.db.get(GovernanceSuggestion, suggestion_id)
        if not row or row.status != "approved":
            return None

        import json as _json

        try:
            chunk_ids = _json.loads(row.chunk_ids)
        except (_json.JSONDecodeError, TypeError):
            chunk_ids = []

        action = row.recommended_action
        result = await self.apply_action(row.kb_id, action, chunk_ids)

        # Phase 3: archive/deactivate 时同步 Chroma 删除 + FTS 更新
        if action in ("archive", "deactivate"):
            await self._sync_chunks_removal(row.kb_id, chunk_ids)

        row.status = "executed"
        row.executed_by = operator or None
        row.executed_at = datetime.utcnow()
        await self.db.commit()
        await self._write_audit(
            row.kb_id,
            suggestion_id,
            "executed",
            operator=operator,
            chunk_ids=row.chunk_ids,
            detail=f"执行动作: {action}, 影响 {result.get('applied', 0)} 个chunk",
        )
        return result

    async def verify_suggestion(
        self,
        suggestion_id: str,
        *,
        operator: str = "",
    ) -> GovernanceSuggestion | None:
        """验证执行结果（executed → verified）。"""
        row = await self.db.get(GovernanceSuggestion, suggestion_id)
        if not row or row.status != "executed":
            return None
        row.status = "verified"
        row.verified_by = operator or None
        row.verified_at = datetime.utcnow()
        await self.db.commit()
        await self._write_audit(
            row.kb_id,
            suggestion_id,
            "verified",
            operator=operator,
            chunk_ids=row.chunk_ids,
            detail=f"验证执行结果: {row.title}",
        )
        return row

    async def rollback_suggestion(
        self,
        suggestion_id: str,
        *,
        operator: str = "",
    ) -> dict | None:
        """回退建议到上一个状态（误操作恢复）。

        支持: approved→pending | executed→approved | verified→executed | dismissed→pending
        """
        row = await self.db.get(GovernanceSuggestion, suggestion_id)
        if not row:
            return None

        import json as _json

        try:
            chunk_ids = _json.loads(row.chunk_ids)
        except (_json.JSONDecodeError, TypeError):
            chunk_ids = []

        prev_status = row.status
        if row.status == "approved":
            row.status = "pending"
            row.approved_by = None
            row.approved_at = None
        elif row.status == "executed":
            row.status = "approved"
            row.executed_by = None
            row.executed_at = None
            action = row.recommended_action
            if action in ("archive", "deactivate"):
                for cid in chunk_ids:
                    chunk = await self.db.get(Chunk, cid)
                    if chunk and not chunk.is_active:
                        await ChunkService(self.db).toggle_status(cid, True)
        elif row.status == "verified":
            row.status = "executed"
            row.verified_by = None
            row.verified_at = None
        elif row.status == "dismissed":
            row.status = "pending"
        else:
            return None

        await self.db.commit()
        await self._write_audit(
            row.kb_id,
            suggestion_id,
            "reverted",
            operator=operator,
            chunk_ids=row.chunk_ids,
            detail=f"回退治理建议: {row.title}（{prev_status} → {row.status}）",
        )
        return {"status": row.status, "prev_status": prev_status}

    async def _sync_chunks_removal(self, kb_id: str, chunk_ids: list[str]) -> None:
        """归档/禁用时同步删除 Chroma 向量 + FTS 索引。"""
        try:
            collection = get_collection(kb_id)
            valid_ids = [cid for cid in chunk_ids if cid]
            if valid_ids:
                collection.delete(ids=valid_ids)
        except Exception as exc:
            logger.warning("governance: Chroma sync failed kb=%s: %s", kb_id, exc)

        try:
            from .fts_service import upsert_chunk_fts

            for cid in chunk_ids:
                await upsert_chunk_fts(
                    self.db,
                    cid,
                    kb_id,
                    "",
                    active=False,
                )
        except Exception as exc:
            logger.warning("governance: FTS sync failed kb=%s: %s", kb_id, exc)

    async def get_audit_log(
        self,
        kb_id: str,
        *,
        action: str | None = None,
        limit: int = 50,
    ) -> list[GovernanceAuditLog]:
        """查询治理审计日志（可按动作筛选）。"""
        q = select(GovernanceAuditLog).where(GovernanceAuditLog.kb_id == kb_id)
        if action:
            q = q.where(GovernanceAuditLog.action == action)
        q = q.order_by(GovernanceAuditLog.created_at.desc()).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())


def _suggestion(
    *,
    stype: str,
    title: str,
    description: str,
    chunk_ids: list[str],
    action: str,
    severity: str,
    preview: str,
) -> dict[str, Any]:
    """构造单条治理建议 dict。

    参数:
        stype: 建议类型
        title: 标题
        description: 说明
        chunk_ids: 关联 chunk
        action: 推荐动作
        severity: info | warning | error
        preview: 内容预览

    返回:
        建议 dict
    """
    return {
        "id": f"{stype}:{uuid.uuid4().hex[:12]}",
        "type": stype,
        "title": title,
        "description": description,
        "chunk_ids": chunk_ids,
        "recommended_action": action,
        "severity": severity,
        "content_preview": preview,
    }
