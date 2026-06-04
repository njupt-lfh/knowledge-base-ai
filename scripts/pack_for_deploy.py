"""项目打包脚本 — 跨平台，生成可直接迁移的压缩包
用法: python scripts/pack_for_deploy.py
输出: knowledge-base-ai-portable.zip

打包前自动清理测试知识库与孤儿数据，确保新机器上只有正式知识库。
"""
import shutil
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "knowledge-base-ai-portable.zip"
DB = ROOT / "data" / "knowledge_base.db"

EXCLUDE = {
    "node_modules", "__pycache__", ".pytest_cache", ".coverage",
    ".claude", ".git", "dist", ".vite",
}

# ── 打包前清理 ──────────────────────────────────────────────
def cleanup_test_data():
    """删除 pytest 产生的测试知识库与孤儿数据，只保留正式 KB。"""
    if not DB.exists():
        return
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys = ON")

    # 删除测试 KB（ID 以 "kb-" 开头，pytest fixture 生成）
    c = conn.execute("DELETE FROM knowledge_bases WHERE id LIKE 'kb-%'")
    deleted_kbs = c.rowcount

    # 级联删除孤儿数据
    conn.execute(
        "DELETE FROM conversations WHERE knowledge_base_id "
        "NOT IN (SELECT id FROM knowledge_bases)"
    )
    conn.execute(
        "DELETE FROM knowledge_gaps WHERE kb_id "
        "NOT IN (SELECT id FROM knowledge_bases)"
    )
    conn.execute(
        "DELETE FROM chunk_feedback WHERE kb_id "
        "NOT IN (SELECT id FROM knowledge_bases)"
    )
    conn.execute(
        "DELETE FROM kg_relations WHERE knowledge_base_id "
        "NOT IN (SELECT id FROM knowledge_bases)"
    )
    conn.execute(
        "DELETE FROM knowledge_conflicts WHERE knowledge_base_id "
        "NOT IN (SELECT id FROM knowledge_bases)"
    )
    conn.execute(
        "DELETE FROM chunk_quality WHERE chunk_id "
        "NOT IN (SELECT id FROM chunks)"
    )
    conn.commit()

    remaining = conn.execute("SELECT count(*) FROM knowledge_bases").fetchone()[0]
    print(f"    清理: 删除 {deleted_kbs} 个测试 KB, 剩余 {remaining} 个正式 KB")
    for row in conn.execute(
        "SELECT substr(id, 1, 8), name FROM knowledge_bases ORDER BY name"
    ):
        print(f"      {row[0]}  {row[1]}")
    conn.close()


# ── 打包主流程 ──────────────────────────────────────────────
print("=== 打包 KnowledgeBase AI 项目 ===")

# 0. 清理
print("[0/5] 清理测试数据...")
cleanup_test_data()

files_to_pack: list[tuple[Path, str]] = []

# 1. 收集源代码
print("[1/5] 收集源代码...")
for src_dir in ["backend", "frontend", "docs"]:
    d = ROOT / src_dir
    if not d.exists():
        continue
    for f in d.rglob("*"):
        if any(ex in f.parts for ex in EXCLUDE):
            continue
        if f.is_file():
            arcname = str(f.relative_to(ROOT))
            files_to_pack.append((f, arcname))

# 根目录文件
for name in [".env.example", ".gitignore", "README.md"]:
    f = ROOT / name
    if f.exists():
        files_to_pack.append((f, name))

# 2. 复制数据（核心）
print("[2/5] 复制数据目录...")
for data_dir in ["data", "chroma_data", "uploads"]:
    d = ROOT / data_dir
    if not d.exists():
        continue
    for f in d.rglob("*"):
        if f.is_file():
            files_to_pack.append((f, str(f.relative_to(ROOT))))

# 3. .env 配置
print("[3/5] 复制配置...")
env_file = ROOT / ".env"
if env_file.exists():
    files_to_pack.append((env_file, ".env"))

# 4. 压缩
print("[4/5] 压缩中...")
written = set()
with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
    for src, arcname in files_to_pack:
        if arcname in written:
            continue
        written.add(arcname)
        zf.write(src, arcname)

size_mb = PACK.stat().st_size / (1024 * 1024)
print(f"[5/5] 完成! → {PACK} ({size_mb:.1f} MB)")
print()
print("新机器上解压后:")
print("  1. 编辑 .env，填入 API 密钥")
print("  2. cd backend && pip install -r requirements.txt")
print("  3. cd frontend && npm install")
print("  4. cd backend && uvicorn app.main:app --reload --port 8080 --host 0.0.0.0")
print("  5. cd frontend && npm run dev")
print("  6. 浏览器打开 http://localhost:5173")
