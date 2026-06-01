"""eval_qa_dataset.json 校验集成测试。

验证内容：
  - eval_qa_dataset.json 格式与子进程校验

运行方式（在 backend 目录）:
  pytest tests/test_validate_eval_dataset.py -v

预期结果：全部用例通过。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "eval_qa_dataset.json"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_eval_dataset.py"


def test_eval_dataset_file_exists_and_valid():
    """调用 validate_eval_dataset.py 子进程；CI 环境跳过 chunk DB 校验。"""
    assert DATA.exists()
    # CI 空库无 chunk 数据，仅校验 JSON schema
    skip_db = os.environ.get("CI", "") != ""
    cmd = [sys.executable, str(SCRIPT)]
    if skip_db:
        cmd.append("--skip-db")
    proc = subprocess.run(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(data["samples"]) >= 20
