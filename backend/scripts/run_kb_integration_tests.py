#!/usr/bin/env python3
"""对各知识库执行标签、AI 对话、提炼知识等集成测试，丰富数据驾驶舱统计。"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://localhost:8082"
TIMEOUT_CHAT = 180
TIMEOUT_DEFAULT = 60

# 每个知识库：标签、检索词、多轮问答
KB_TEST_PLAN: dict[str, dict] = {
    "AI 技术文档库": {
        "tags": ["机器学习", "大模型"],
        "searches": ["什么是 RAG", "Transformer 原理"],
        "questions": [
            "什么是检索增强生成 RAG？",
            "Embedding 向量在知识库中起什么作用？",
            "大语言模型有哪些常见应用场景？",
            "如何评估一个 AI 问答系统的质量？",
            "知识库分块大小应该如何选择？",
            "向量数据库和关系数据库有什么区别？",
        ],
    },
    "健康养生": {
        "tags": ["饮食", "运动"],
        "searches": ["均衡饮食", "睡眠质量"],
        "questions": [
            "成年人每天应该怎么安排饮食？",
            "每周运动多少次比较合适？",
            "改善睡眠有哪些实用方法？",
            "轻微感冒在家可以怎么处理？",
            "久坐办公如何保护颈椎？",
            "春季养生需要注意什么？",
        ],
    },
    "美食烹饪": {
        "tags": ["菜谱", "食材保存"],
        "searches": ["调味技巧", "肉类保存"],
        "questions": [
            "新手炒菜如何控制火候？",
            "常见的中式调味顺序是什么？",
            "叶菜如何保存更新鲜？",
            "炖汤和快炒分别适合什么食材？",
            "如何判断肉类是否熟透？",
            "剩菜的正确保存和复热方式？",
        ],
    },
    "居家生活": {
        "tags": ["清洁", "收纳"],
        "searches": ["厨房清洁", "衣物收纳"],
        "questions": [
            "厨房油污怎么清洁更高效？",
            "小户型收纳有哪些原则？",
            "冰箱使用有哪些注意事项？",
            "跳闸了应该怎么排查？",
            "卫生间防霉防潮有什么办法？",
            "换季衣物如何收纳防虫？",
        ],
    },
    "理财消费": {
        "tags": ["预算", "防诈骗"],
        "searches": ["应急储蓄", "保险基础"],
        "questions": [
            "家庭预算怎么制定比较合理？",
            "应急金应该存多少？",
            "普通人应该先配置哪些保险？",
            "常见的电信诈骗有哪些套路？",
            "网购退款诈骗如何识别？",
            "年轻人理财应该避免哪些误区？",
        ],
    },
    "出行旅游": {
        "tags": ["签证", "应急"],
        "searches": ["行前准备", "护照丢失"],
        "questions": [
            "出国旅行行前需要准备哪些证件？",
            "航班延误时乘客有哪些权益？",
            "旅途中如何保管财物更安全？",
            "护照丢失在国外应该怎么处理？",
            "自由行如何规划交通和住宿？",
            "高原旅行需要注意什么？",
        ],
    },
    "法律常识": {
        "tags": ["租房", "劳动权益"],
        "searches": ["押金退还", "消费维权"],
        "questions": [
            "租房签合同要注意哪些条款？",
            "房东不退押金怎么办？",
            "试用期工资有什么法律规定？",
            "网购商品有问题如何维权？",
            "12315 投诉流程是怎样的？",
            "劳动合同未签有哪些风险？",
        ],
    },
    "育儿教育": {
        "tags": ["安全", "习惯培养"],
        "searches": ["亲子阅读", "屏幕时间"],
        "questions": [
            "0-3 岁宝宝居家安全防护要点？",
            "如何培养孩子自主收纳习惯？",
            "学龄儿童每天屏幕时间怎么控制？",
            "孩子之间发生冲突家长怎么处理？",
            "如何建立固定的作业时间？",
            "幼儿园阶段适合哪些亲子活动？",
        ],
    },
    "宠物养护": {
        "tags": ["喂养", "疫苗"],
        "searches": ["换粮", "驱虫"],
        "questions": [
            "猫咪日常喂养有哪些注意事项？",
            "幼犬疫苗一般怎么安排？",
            "宠物换粮为什么要逐步过渡？",
            "猫狗哪些症状需要立即就医？",
            "室内养猫如何减少异味？",
            "遛狗时有哪些安全规范？",
        ],
    },
    "数码技巧": {
        "tags": ["手机", "网络安全"],
        "searches": ["数据备份", "双重验证"],
        "questions": [
            "手机如何开启查找设备和备份？",
            "电脑重要文件怎么做 3-2-1 备份？",
            "什么是双重验证，如何开启？",
            "公共 Wi-Fi 下有哪些安全风险？",
            "如何识别钓鱼短信和链接？",
            "旧手机出售前如何清除个人数据？",
        ],
    },
}


def api(method: str, path: str, body: dict | None = None, timeout: int = TIMEOUT_DEFAULT):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def chat_stream(conv_id: str, message: str) -> dict:
    url = f"{BASE_URL}/api/conversations/{conv_id}/chat"
    body = json.dumps({"message": message, "knowledge_base_id": ""}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    text_parts: list[str] = []
    sources: list = []
    with urllib.request.urlopen(req, timeout=TIMEOUT_CHAT) as resp:
        buffer = ""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "text":
                    text_parts.append(event.get("content", ""))
                elif event.get("type") == "sources":
                    sources = event.get("sources") or []
    return {"answer": "".join(text_parts), "sources": sources}


def wait_doc_completed(kb_id: str, doc_id: str, max_wait: int = 120) -> bool:
    for _ in range(max_wait // 3):
        doc = api("GET", f"/api/knowledge-bases/{kb_id}/documents/{doc_id}")
        if doc["status"] == "completed":
            return True
        if doc["status"] == "error":
            return False
        time.sleep(3)
    return False


def should_skip_kb(kb_id: str) -> tuple[bool, str]:
    """已测过的知识库跳过，避免重复调用 LLM。"""
    convs = api("GET", f"/api/knowledge-bases/{kb_id}/conversations")
    if len(convs) < 2:
        return False, ""
    msg_total = 0
    for conv in convs[:5]:
        msgs = api("GET", f"/api/conversations/{conv['id']}/messages")
        msg_total += len(msgs)
    if msg_total >= 10:
        return True, f"已有 {len(convs)} 个对话 / {msg_total}+ 条消息"
    return False, ""


def test_kb(kb: dict) -> dict:
    name = kb["name"]
    kb_id = kb["id"]
    plan = KB_TEST_PLAN.get(name)
    if not plan:
        return {"kb": name, "skipped": True, "reason": "无测试计划"}

    skip, reason = should_skip_kb(kb_id)
    if skip:
        print(f"\n跳过 {name}: {reason}")
        return {"kb": name, "skipped": True, "reason": reason}

    result = {
        "kb": name,
        "kb_id": kb_id,
        "tags_created": 0,
        "docs_tagged": 0,
        "searches": 0,
        "conversations": 0,
        "messages": 0,
        "extract_attempts": 0,
        "extract_saved": 0,
        "shares": 0,
        "errors": [],
    }

    print(f"\n{'='*60}\n测试知识库: {name} ({kb_id})", flush=True)

    # 1. 创建标签
    existing_tags = {t["name"]: t["id"] for t in api("GET", f"/api/knowledge-bases/{kb_id}/tags")}
    tag_ids: list[str] = []
    for tag_name in plan["tags"]:
        if tag_name in existing_tags:
            tag_ids.append(existing_tags[tag_name])
            print(f"  [标签] 已存在: {tag_name}", flush=True)
            continue
        try:
            tag = api("POST", f"/api/knowledge-bases/{kb_id}/tags", {"name": tag_name})
            tag_ids.append(tag["id"])
            result["tags_created"] += 1
            print(f"  [标签] 创建: {tag_name}", flush=True)
        except RuntimeError as exc:
            result["errors"].append(f"标签 {tag_name}: {exc}")
            print(f"  [标签] 失败: {tag_name} -> {exc}", flush=True)

    # 2. 给文档打标签
    docs_resp = api("GET", f"/api/knowledge-bases/{kb_id}/documents?page_size=50")
    completed_docs = [d for d in docs_resp["items"] if d["status"] == "completed"]
    for doc in completed_docs[: min(3, len(completed_docs))]:
        if not tag_ids:
            break
        try:
            api(
                "POST",
                f"/api/knowledge-bases/{kb_id}/documents/{doc['id']}/tags",
                {"tag_ids": tag_ids[:2]},
            )
            result["docs_tagged"] += 1
            print(f"  [标签] 文档「{doc['filename']}」已打标")
        except RuntimeError as exc:
            result["errors"].append(f"文档打标 {doc['filename']}: {exc}")

    # 3. 检索测试（增加 hit_count）
    for query in plan["searches"]:
        try:
            api("POST", f"/api/knowledge-bases/{kb_id}/search", {"query": query, "top_k": 5})
            result["searches"] += 1
            print(f"  [检索] {query}")
            time.sleep(0.5)
        except RuntimeError as exc:
            result["errors"].append(f"检索 {query}: {exc}")

    # 4. 多轮 AI 对话（两个会话）
    questions = plan["questions"]
    mid = len(questions) // 2
    conv_specs = [("对话A", questions[: mid + 1]), ("对话B", questions[mid + 1 :])]

    conv_ids: list[str] = []
    for conv_label, qs in conv_specs:
        if not qs:
            continue
        try:
            conv = api("POST", f"/api/knowledge-bases/{kb_id}/chat")
            conv_id = conv["id"]
            conv_ids.append(conv_id)
            result["conversations"] += 1
            print(f"  [对话] 创建{conv_label}: {conv_id[:8]}...")
        except RuntimeError as exc:
            result["errors"].append(f"创建对话: {exc}")
            continue

        for i, q in enumerate(qs, 1):
            try:
                print(f"  [问答] {conv_label} Q{i}: {q[:40]}...")
                reply = chat_stream(conv_id, q)
                result["messages"] += 1
                src_n = len(reply.get("sources") or [])
                ans_preview = (reply.get("answer") or "")[:60].replace("\n", " ")
                print(f"         A: {ans_preview}... (引用 {src_n} 条)")
                time.sleep(1)
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(f"问答 {q[:20]}: {exc}")
                print(f"  [问答] 失败: {exc}")

    # 5. 提炼知识
    if conv_ids:
        conv_id = conv_ids[0]
        try:
            result["extract_attempts"] += 1
            extracted = api("POST", f"/api/conversations/{conv_id}/extract-knowledge")
            if extracted.get("has_knowledge"):
                title = extracted.get("title", "提炼知识")
                content = extracted.get("content", "")
                manual = api(
                    "POST",
                    f"/api/knowledge-bases/{kb_id}/documents/manual",
                    {"title": f"[提炼] {title}", "content": content},
                )
                if wait_doc_completed(kb_id, manual["id"]):
                    result["extract_saved"] += 1
                    print(f"  [提炼] 已入库: {title}")
                else:
                    print(f"  [提炼] 入库处理中或失败: {title}")
            else:
                print("  [提炼] 本轮对话未检测到可提炼知识")
        except RuntimeError as exc:
            result["errors"].append(f"提炼知识: {exc}")
            print(f"  [提炼] 失败: {exc}")

    # 6. 分享链接
    if len(conv_ids) > 1:
        try:
            api("POST", f"/api/conversations/{conv_ids[1]}/share")
            result["shares"] += 1
            print("  [分享] 已生成分享链接")
        except RuntimeError as exc:
            result["errors"].append(f"分享: {exc}")

    return result


def main() -> int:
    print(f"API: {BASE_URL}")
    kbs = api("GET", "/api/knowledge-bases?page_size=50")["items"]
    print(f"共 {len(kbs)} 个知识库待测试")

    results = []
    for kb in kbs:
        results.append(test_kb(kb))

    report_path = Path(__file__).resolve().parents[2] / "data" / "kb_test_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}\n测试汇总")
    total_msgs = sum(r.get("messages", 0) for r in results)
    total_tags = sum(r.get("tags_created", 0) for r in results)
    total_extract = sum(r.get("extract_saved", 0) for r in results)
    total_errors = sum(len(r.get("errors", [])) for r in results)
    for r in results:
        if r.get("skipped"):
            print(f"  - {r['kb']}: 跳过")
        else:
            print(
                f"  - {r['kb']}: 对话{r['messages']}轮, 标签{r['tags_created']}个, "
                f"打标文档{r['docs_tagged']}篇, 提炼{r['extract_saved']}篇"
            )
    print(f"\n合计: {total_msgs} 轮问答, {total_tags} 个标签, {total_extract} 篇提炼入库, {total_errors} 个错误")
    print(f"报告: {report_path}")

    # 验证驾驶舱数据
    try:
        overview = api("GET", "/api/stats/overview")
        print(f"\n驾驶舱概览: 知识库 {overview.get('total_knowledge_bases')} 个, "
              f"总命中 {overview.get('total_hits')} 次")
    except RuntimeError as exc:
        print(f"\n驾驶舱概览获取失败: {exc}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
