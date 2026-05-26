import os

import pytest

os.environ.setdefault("LLM_MOCK_MODE", "true")


@pytest.fixture
def tmp_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("Hello world.\nSecond line.", encoding="utf-8")
    return p
