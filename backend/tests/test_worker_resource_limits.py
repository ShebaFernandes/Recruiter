import resource

from django.test import override_settings
from talent.management.commands.process_resume_job import _tighten_resource_limit
from talent.worker_runtime import _limit_child_resources


def test_worker_child_has_memory_and_cpu_hard_limits(monkeypatch):
    calls = {}
    monkeypatch.setattr(resource, 'setrlimit', lambda kind, limit: calls.setdefault(kind, limit))
    with override_settings(RESUME_WORKER_CHILD_MEMORY_MB=320,
                           RESUME_PROCESS_HARD_TIMEOUT_SECONDS=240):
        _limit_child_resources()
    assert calls[resource.RLIMIT_AS] == (320 * 1024 * 1024,) * 2
    assert calls[resource.RLIMIT_CPU] == (235, 235)


def test_child_does_not_raise_supervisor_hard_limits(monkeypatch):
    inherited = {
        resource.RLIMIT_CPU: (235, 235),
        resource.RLIMIT_AS: (320 * 1024 * 1024,) * 2,
    }
    applied = {}
    monkeypatch.setattr(resource, 'getrlimit', inherited.__getitem__)

    def set_limit(kind, limits):
        if limits[1] > inherited[kind][1]:
            raise ValueError('not allowed to raise maximum limit')
        applied[kind] = limits

    monkeypatch.setattr(resource, 'setrlimit', set_limit)
    _tighten_resource_limit(resource.RLIMIT_CPU, 240)
    _tighten_resource_limit(resource.RLIMIT_AS, 768 * 1024 * 1024)
    assert applied == inherited


def test_standalone_child_still_applies_its_requested_limit(monkeypatch):
    calls = {}
    monkeypatch.setattr(resource, 'getrlimit', lambda kind: (resource.RLIM_INFINITY,) * 2)
    monkeypatch.setattr(resource, 'setrlimit', lambda kind, limit: calls.setdefault(kind, limit))
    _tighten_resource_limit(resource.RLIMIT_CPU, 240)
    assert calls[resource.RLIMIT_CPU] == (240, 240)
