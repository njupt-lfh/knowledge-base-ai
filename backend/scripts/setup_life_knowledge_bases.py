#!/usr/bin/env python3
"""初始化生活主题知识库

验证内容：
  - 清理旧库并创建 9 个主题库

运行方式（在 backend 目录）:
  python scripts/setup_life_knowledge_bases.py

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
KEEP_KB_NAME = "AI 技术文档库"

THEMED_KBS = [
    {
        "name": "健康养生",
        "description": "饮食、运动、睡眠、常见小毛病",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "美食烹饪",
        "description": "菜谱、食材保存、调味技巧",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "居家生活",
        "description": "清洁、收纳、家电使用、维修常识",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "理财消费",
        "description": "预算、储蓄、保险基础、防诈骗",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "出行旅游",
        "description": "签证、交通、住宿、应急处理",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "法律常识",
        "description": "租房、劳动、消费维权",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "育儿教育",
        "description": "各年龄段习惯、安全、学习",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "宠物养护",
        "description": "喂养、疫苗、常见疾病",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
    {
        "name": "数码技巧",
        "description": "手机、电脑、网络安全",
        "chunk_size": 700,
        "chunk_overlap": 70,
    },
]


def request(method: str, path: str, body: dict | None = None) -> dict | None:
    """HTTP 请求封装，失败时抛出 RuntimeError。"""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return None
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {detail}") from exc


def list_kbs() -> list[dict]:
    """分页获取知识库列表。"""
    data = request("GET", "/api/knowledge-bases?page_size=100")
    return data["items"] if data else []


def main() -> int:
    """脚本 CLI 入口。"""
    print(f"API: {BASE_URL}")
    kbs = list_kbs()
    print(f"当前知识库数量: {len(kbs)}")

    keep = next((kb for kb in kbs if kb["name"] == KEEP_KB_NAME), None)
    if not keep:
        print(f"警告: 未找到「{KEEP_KB_NAME}」，将保留 0 个现有库")
    else:
        print(f"保留: {keep['name']} ({keep['id']})")

    deleted = 0
    for kb in kbs:
        if keep and kb["id"] == keep["id"]:
            continue
        print(f"删除: {kb['name']} ({kb['id']})")
        request("DELETE", f"/api/knowledge-bases/{kb['id']}")
        deleted += 1

    existing_names = {kb["name"] for kb in list_kbs()}
    created = 0
    for spec in THEMED_KBS:
        if spec["name"] in existing_names:
            print(f"跳过（已存在）: {spec['name']}")
            continue
        kb = request("POST", "/api/knowledge-bases", spec)
        print(f"创建: {kb['name']} ({kb['id']})")
        created += 1

    final = list_kbs()
    print("\n完成")
    print(f"  删除: {deleted} 个")
    print(f"  新建: {created} 个")
    print(f"  当前共: {len(final)} 个知识库")
    for kb in final:
        print(f"    - {kb['name']}（文档 {kb['document_count']}）")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
