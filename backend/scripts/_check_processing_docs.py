"""诊断脚本：列出卡在 processing 状态的文档及文件是否存在。

验证内容：
  - 查询 SQLite 中 status='processing' 的文档
  - 对比 backend/uploads 与根目录 uploads 中对应文件是否存在
  - 输出各 status 汇总统计

运行方式（在 backend 目录）:
  python scripts/_check_processing_docs.py

预期结果：打印 processing 文档详情与状态汇总；无断言，仅用于排查。
"""

import sqlite3
from pathlib import Path

# 连接项目根目录下的 SQLite 数据库
DB = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db"
c = sqlite3.connect(DB)

# 查询所有处于 processing 状态的文档
rows = c.execute(
    """
  SELECT d.id, d.filename, d.file_type, d.status, d.file_path, d.file_size,
         d.created_at, d.updated_at, kb.name
  FROM documents d
  LEFT JOIN knowledge_bases kb ON kb.id = d.knowledge_base_id
  WHERE d.status = 'processing'
  ORDER BY d.created_at DESC
"""
).fetchall()
print("processing count", len(rows))
for r in rows:
    print("---")
    print("id", r[0][:8], "file", r[1], "type", r[2])
    print("path", r[4], "size", r[5])
    print("kb", r[8], "created", r[6], "updated", r[7])

# 各状态文档数量汇总
print("\nstatus summary:")
for r in c.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall():
    print(r)

# 检查物理文件是否存在于两个可能的 uploads 目录
print("\nfile existence (backend/uploads vs root/uploads):")
backend_up = Path(__file__).resolve().parents[1] / "uploads"
root_up = Path(__file__).resolve().parents[2] / "uploads"
for r in rows:
    name = Path(r[4] or "").name
    b = backend_up / name
    root = root_up / name
    print(name[:50], "| backend:", b.exists(), "| root:", root.exists())
