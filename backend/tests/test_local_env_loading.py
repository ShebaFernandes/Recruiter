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


def test_local_api_does_not_load_worker_secret(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    secret = tmp_path / 'worker.key'
    secret.write_text('fictional-worker-secret')
    environment = {
        **os.environ,
        'APP_ENV': 'local', 'DEBUG': 'true', 'TESTING': 'false',
        'RESUME_AI_ENABLED': 'false', 'RESUME_AI_API_KEY_FILE': str(secret),
        'GEMINI_API_KEY': 'fictional-legacy-key', 'RESUME_AI_API_KEY': '',
        'ENTER_LOCAL_RESUME_WORKER': 'false',
    }
    source = '''
import json, os, sys
sys.path.insert(0, 'backend')
sys.argv = ['manage.py', sys.argv[1]]
from config import settings
print(json.dumps({'worker_key': settings.RESUME_AI_API_KEY == 'fictional-worker-secret',
                  'legacy_key': bool(settings.GEMINI_API_KEY),
                  'legacy_environment': bool(os.getenv('GEMINI_API_KEY'))}))
'''
    for command in ['runserver', 'run_resume_worker', 'process_resume_job']:
        result = subprocess.run([sys.executable, '-c', source, command], cwd=root,
                                env=environment, capture_output=True, text=True, check=True)
        actual = json.loads(result.stdout)
        worker = command != 'runserver'
        assert actual == {'worker_key': worker, 'legacy_key': worker,
                          'legacy_environment': worker}
    # A missing worker-only file must not prevent the local API from booting.
    secret.unlink()
    subprocess.run([sys.executable, '-c', source, 'runserver'], cwd=root,
                   env=environment, capture_output=True, text=True, check=True)
