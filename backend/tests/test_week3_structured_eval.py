"""Week 3 结构感知分块与 eval_run 服务测试。"""


import pytest
from app.services.chunking_service import (
    StructuredTextChunker,
    build_content_chunks,
)
from app.services.eval_run_service import TREND_METRICS, metric_trend, persist_eval_report


def test_split_markdown_by_headings():
    md = """# Python 入门
第一段内容足够长以便通过最小长度过滤阈值，介绍 Python 基础语法与常用库。

## 异步编程
第二段内容同样足够长，说明 asyncio 与 async/await 的基本用法与注意事项。
"""
    st = StructuredTextChunker(min_chars=50, noise_min_chars=30)
    segs = st.split_markdown(md)
    assert len(segs) >= 2
    assert any("Python 入门" in (s.heading_path or "") for s in segs)
    formatted = [st.format_for_ingest(s) for s in segs]
    assert any(f.startswith("[章节:") for f in formatted)


def test_split_pdf_pages_filters_noise():
    st = StructuredTextChunker(noise_min_chars=30)
    pages = ["短", "这是一段足够长的 PDF 页面正文，用于测试结构分块与噪声过滤逻辑。"]
    segs = st.split_pdf_pages(pages)
    assert len(segs) == 1
    assert segs[0].page_no == 2


def test_build_content_chunks_structured():
    text = "主题段落一。" * 20 + "\n\n" + "主题段落二。" * 20
    parts = build_content_chunks(text, chunk_size=200, structured=True)
    assert len(parts) >= 1


@pytest.mark.asyncio
async def test_persist_eval_report_and_trend():
    from app.core.database import async_session, init_db

    await init_db()
    report = {
        "dataset_version": "v2",
        "config": {"eval_mode": "retrieval_only", "sample_count": 1},
        "aggregate": {
            "sample_count": 1,
            "context_precision_chunk": 0.42,
            "context_recall_mean": 0.88,
        },
        "samples": [
            {
                "id": "t-001",
                "kb_id": "kb1",
                "q_type": "fact",
                "context_recall": 1.0,
                "context_precision_chunk": 0.5,
                "retrieval_hit": True,
            }
        ],
    }
    async with async_session() as db:
        run_id = await persist_eval_report(db, report, ci_phase="week2_v2")
        assert run_id
        points = await metric_trend(
            db, "context_precision_chunk", limit=5, dataset_version="v2"
        )
    assert points[-1]["value"] == pytest.approx(0.42)


def test_trend_metrics_list():
    assert "context_precision_chunk" in TREND_METRICS
