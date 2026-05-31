import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "eval_qa_dataset.json"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_eval_dataset.py"


def test_eval_dataset_file_exists_and_valid():
    """校验数据集格式（CI 空库跳过 chunk ID 验证）。"""
    assert DATA.exists()
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
