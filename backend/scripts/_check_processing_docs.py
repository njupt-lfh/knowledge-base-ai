import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.db"
c = sqlite3.connect(DB)
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
print("\nstatus summary:")
for r in c.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall():
    print(r)

print("\nfile existence (backend/uploads vs root/uploads):")
backend_up = Path(__file__).resolve().parents[1] / "uploads"
root_up = Path(__file__).resolve().parents[2] / "uploads"
for r in rows:
    name = Path(r[4] or "").name
    b = backend_up / name
    root = root_up / name
    print(name[:50], "| backend:", b.exists(), "| root:", root.exists())
