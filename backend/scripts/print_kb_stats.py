import sqlite3
from pathlib import Path

db = sqlite3.connect(Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db")
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
