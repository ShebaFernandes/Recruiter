import importlib.util
import sys
from pathlib import Path


def test_twenty_fixture_offline_resume_benchmark():
    path = Path(__file__).resolve().parents[2] / "scripts" / "resume_accuracy_benchmark.py"
    spec = importlib.util.spec_from_file_location("resume_accuracy_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    result = module.run()
    assert result["fixture_count"] >= 20
    assert result["employer_recall"] == 1
    assert result["employment_role_recall"] == 1
    assert result["date_accuracy"] == 1
    assert result["unsupported_rows"] == 0
    assert result["duplicate_rows"] == 0
    assert result["processing_errors"] == 0
