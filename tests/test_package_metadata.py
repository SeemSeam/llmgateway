from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_include_httpx_http2_extra() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]

    assert "httpx[http2]>=0.24" in dependencies
