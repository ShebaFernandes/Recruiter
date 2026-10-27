import resource

from django.test import override_settings
from talent.worker_runtime import _limit_child_resources


def test_worker_child_has_memory_and_cpu_hard_limits(monkeypatch):
    calls = {}
    monkeypatch.setattr(resource, 'setrlimit', lambda kind, limit: calls.setdefault(kind, limit))
    with override_settings(RESUME_WORKER_CHILD_MEMORY_MB=320,
                           RESUME_PROCESS_HARD_TIMEOUT_SECONDS=240):
        _limit_child_resources()
    assert calls[resource.RLIMIT_AS] == (320 * 1024 * 1024,) * 2
    assert calls[resource.RLIMIT_CPU] == (235, 235)
