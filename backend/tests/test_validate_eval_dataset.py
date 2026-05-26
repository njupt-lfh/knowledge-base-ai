import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "eval_qa_dataset.json"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_eval_dataset.py"


def test_eval_dataset_file_exists_and_valid():
    assert DATA.exists()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(data["samples"]) >= 20
