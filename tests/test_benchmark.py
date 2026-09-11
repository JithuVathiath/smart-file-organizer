from __future__ import annotations

import importlib.util
from pathlib import Path


def _benchmark_module():
    path = Path(__file__).parents[1] / "benchmarks/run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_small_benchmark_case() -> None:
    result = _benchmark_module().run_case(12)
    assert result["files"] == 12
    assert result["planned_moves"] == 12
    assert result["scan_files_per_second"] > 0
