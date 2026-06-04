#!/bin/bash
# 项目打包脚本 — 生成可直接在新机器上运行的完整压缩包
# 用法: bash scripts/pack_for_deploy.sh
# 输出: knowledge-base-ai-portable.zip

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACK="$ROOT/knowledge-base-ai-portable.zip"

echo "=== 打包 KnowledgeBase AI 项目 ==="

# 临时目录
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

DST="$TMP/knowledge-base-ai"
mkdir -p "$DST"

# 1. 源代码
echo "[1/6] 复制源代码..."
rsync -a --exclude 'node_modules' --exclude '__pycache__' --exclude '.pytest_cache' \
      --exclude '.coverage' --exclude '.claude' --exclude '.git' \
      "$ROOT/backend" "$DST/"
rsync -a --exclude 'node_modules' --exclude '__pycache__' \
      --exclude '.claude' \
      "$ROOT/frontend" "$DST/"
cp "$ROOT/.env.example" "$DST/.env.example"
cp "$ROOT/.gitignore" "$DST/.gitignore"
cp "$ROOT/README.md" "$DST/README.md"
cp -r "$ROOT/docs" "$DST/docs"

# 2. 数据（核心）
echo "[2/6] 复制数据库 + 向量 + 上传文件..."
cp -r "$ROOT/data" "$DST/data"
cp -r "$ROOT/chroma_data" "$DST/chroma_data"
cp -r "$ROOT/uploads" "$DST/uploads"

# 3. 移除 .env 中的 API Key（安全）
echo "[3/6] 清理密钥..."
if [ -f "$DST/.env" ]; then
  sed -i 's/^VOLCENGINE_API_KEY=.*/VOLCENGINE_API_KEY=your_api_key_here/' "$DST/.env"
  sed -i 's/^GRAPH_EXTRACTION_MODEL=.*/GRAPH_EXTRACTION_MODEL=/' "$DST/.env"
fi

# 4. 生成启动说明
echo "[4/6] 生成启动说明..."
cat > "$DST/快速启动.txt" << 'STARTUP'
========================================
  KnowledgeBase AI — 快速启动指南
========================================

环境要求:
  - Python >= 3.11
  - Node.js >= 18

1. 配置 API 密钥
   编辑 .env.example，填入火山引擎 API 凭证:
     VOLCENGINE_API_KEY=你的API_Key
     VOLCENGINE_LLM_MODEL=你的对话接入点ID
     VOLCENGINE_EMBEDDING_MODEL=你的嵌入接入点ID
   保存为 .env

2. 安装后端依赖
   cd backend
   pip install -r requirements.txt
   pip install -r requirements-dev.txt     (可选，跑测试需要)
   pip install -r requirements-eval.txt    (可选，跑评测需要)

3. 安装前端依赖
   cd frontend
   npm install

4. 启动后端 (端口 8082)
   cd backend
   uvicorn app.main:app --reload --port 8082 --host 0.0.0.0

5. 启动前端 (端口 5173)
   cd frontend
   npm run dev

6. 访问
   打开浏览器: http://localhost:5173

数据说明:
  - 所有知识库、文档、对话、评测数据已内置
  - data/       → SQLite 数据库 (元数据、FTS5、图谱)
  - chroma_data/ → 向量嵌入 (Chroma)
  - uploads/    → 上传的原始文件

故障排查:
  - 如端口冲突: 改 backend 端口后需同步改 frontend/.env 中的 VITE_API_BASE
  - 如缺少依赖: pip install -r requirements.txt
  - 如 Chroma 报错: 确认 chroma_data/ 目录在 backend/ 同级
STARTUP

# 5. 打包
echo "[5/6] 压缩..."
cd "$TMP"
zip -r "$PACK" knowledge-base-ai -x "*.pyc" -x "__pycache__/*" -x ".DS_Store"

# 6. 完成
SIZE=$(du -sh "$PACK" | cut -f1)
echo "[6/6] 完成!"
echo "  文件: $PACK"
echo "  大小: $SIZE"
echo ""
echo "新机器上解压后按 快速启动.txt 操作即可。"
