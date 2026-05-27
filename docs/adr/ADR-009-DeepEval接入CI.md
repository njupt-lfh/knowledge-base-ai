# ADR-009: DeepEval 接入 CI（Phase 2.4）

**状态**：已采纳  
**日期**：2026-05-26

## 决策

| 项 | 方案 |
|----|------|
| 指标 | `HallucinationMetric` + `ContextualRelevancyMetric` |
| Judge | `VolcengineDeepEvalLLM` 复用 `LLMService`（豆包） |
| CI 默认 | **offline 代理指标**（确定性、无 API），门禁可过 |
| 定时/手动 | `--live --retrieval` 跑真实 DeepEval + Knowledge Retention |
| 回归 | `check_knowledge_retention`：recall 不低于基线 85% |
| 冒烟集 | `backend/tests/fixtures/eval_smoke_samples.json` |

## 关键文件

- `backend/app/eval/deepeval_runner.py`
- `backend/scripts/run_deepeval_ci.py`
- `backend/scripts/run_rag_eval.py`（`--deepeval`）
- `.github/workflows/ci.yml`
- `backend/requirements-eval.txt`（+ deepeval）

## 验收

```bash
cd backend
python scripts/verify_phase2_4.py
python scripts/run_deepeval_ci.py
python -m pytest tests/test_deepeval_runner.py -v
```

## 与 Phase 2 出口

- **Hallucination / Contextual Relevancy**：CI 默认 offline；生产评测 `--live`
- **Knowledge Retention**：`run_rag_eval.py --deepeval` 或 `run_deepeval_ci.py --retrieval`
- **Context Recall +15%**：需本地全量 `run_rag_eval.py --retrieval-only` 对比 ADR-000 基线
