import os

from config.settings import _load_local_env


def test_local_env_loader_reads_values_without_executing_or_overriding(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# synthetic settings only\n"
        "ANTHROPIC_API_KEY='synthetic-secret'\n"
        "AI_PROVIDER=anthropic\n"
        "INVALID LINE\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_PROVIDER", "deterministic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    _load_local_env(dotenv)

    assert os.environ["ANTHROPIC_API_KEY"] == "synthetic-secret"
    assert os.environ["AI_PROVIDER"] == "deterministic"
