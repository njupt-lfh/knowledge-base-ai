"""统计脚本：导出各知识库的文档/对话/消息/标签/命中数。

验证内容：
  - 从 SQLite 聚合每个知识库的关键指标
  - 写入 data/kb_test_summary.txt 并打印到控制台

运行方式（在 backend 目录）:
  python scripts/print_kb_stats.py

预期结果：打印表格化统计并生成 kb_test_summary.txt；无断言。
"""

import sqlite3
from pathlib import Path

# 连接项目数据库
db = sqlite3.connect(Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db")

# 按知识库聚合文档数、对话数、消息数、标签数、chunk 命中总数
rows = db.execute(
    """
    SELECT kb.name,
           (SELECT COUNT(*) FROM documents d WHERE d.knowledge_base_id = kb.id) AS docs,
           (SELECT COUNT(*) FROM conversations c WHERE c.knowledge_base_id = kb.id) AS convs,
           (SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.knowledge_base_id = kb.id) AS msgs,
           (SELECT COUNT(*) FROM tags t WHERE t.knowledge_base_id = kb.id) AS tags,
           COALESCE((SELECT SUM(ch.hit_count) FROM chunks ch WHERE ch.knowledge_base_id = kb.id), 0) AS hits
    FROM knowledge_bases kb
    ORDER BY kb.name
    """
).fetchall()

lines = ["知识库 | 文档 | 对话 | 消息 | 标签 | 命中"]
for r in rows:
    lines.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}")

out = Path(__file__).resolve().parents[2] / "data" / "kb_test_summary.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
