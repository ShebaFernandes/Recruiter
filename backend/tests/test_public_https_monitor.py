"""Off-host monitor tests: synthetic responses only, no external network or AWS."""

import hashlib
import json
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=[0, 2])
def probe(request):
    path = ROOT / "deploy/public_https_monitor.py"
    scope = {"__name__": "synthetic_probe", "__file__": str(path)}
    exec(compile(path.read_text(), str(path), "exec", optimize=request.param), scope)
    return SimpleNamespace(**scope), scope


def response(probe, monkeypatch, status=200, body=b"", content_type="text/html"):
    module, scope = probe
    result = Mock(status=status)
    result.read.return_value = body
    result.getheader.return_value = content_type
    conn = Mock()
    conn.getresponse.return_value = result
    factory = Mock(return_value=conn)
    monkeypatch.setitem(scope, "PublicHTTPSConnection", factory)
    return conn, factory, result


@pytest.mark.parametrize("status", [301, 302, 401, 403, 404, 500, 503])
def test_bad_status_never_follows_redirects(probe, monkeypatch, status):
    conn, _, result = response(probe, monkeypatch, status=status)
    assert not probe[0].check_endpoint("/", "frontend")
    result.read.assert_not_called()
    conn.request.assert_called_once()
    conn.close.assert_called_once()


def test_frontend_and_tls_configuration(probe, monkeypatch):
    _, factory, _ = response(probe, monkeypatch, body=b'<html><div id="root"></div></html>')
    assert probe[0].check_endpoint("/", "frontend")
    context = factory.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


@pytest.mark.parametrize(
    "data,expected",
    [
        ({"status": "ready", "database": "ok"}, True),
        ({"status": "ready", "database": "down"}, False),
        ({"status": "ok"}, False),
        ([], False),
        (None, False),
    ],
)
def test_readiness_contract(probe, monkeypatch, data, expected):
    response(probe, monkeypatch, body=json.dumps(data).encode(), content_type="application/json")
    assert probe[0].check_endpoint("/api/v1/health/ready/", "readiness") is expected


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"not-json", "application/json"),
        (b"x" * 65537, "application/json"),
        (b'{"status":"ready","database":"ok"}', "text/html"),
    ],
)
def test_invalid_or_oversized_body(probe, monkeypatch, body, content_type):
    response(probe, monkeypatch, body=body, content_type=content_type)
    assert not probe[0].check_endpoint("/api/v1/health/ready/", "readiness")


@pytest.mark.parametrize(
    "error",
    [
        ssl.SSLCertVerificationError("SECRET certificate failure"),
        socket.timeout("SECRET timeout"),
        socket.gaierror("SECRET DNS failure"),
    ],
)
def test_network_failure_is_sanitized(probe, monkeypatch, capsys, error):
    conn, _, _ = response(probe, monkeypatch)
    conn.request.side_effect = error
    assert not probe[0].check_endpoint("/", "frontend")
    assert "SECRET" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "addresses",
    [[], ["127.0.0.1"], ["169.254.169.254"], ["10.0.0.1"], ["3.26.28.4", "192.168.0.1"]],
)
def test_private_or_empty_dns_rejected(probe, monkeypatch, addresses):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses],
    )
    with pytest.raises(ValueError):
        probe[0].public_address("staging.enter.careers")


def test_connection_uses_validated_ip_with_original_sni(probe, monkeypatch):
    module, scope = probe
    monkeypatch.setitem(scope, "public_address", lambda host: "3.26.28.4")
    raw = Mock()
    connect = Mock(return_value=raw)
    monkeypatch.setattr(socket, "create_connection", connect)
    conn = module.PublicHTTPSConnection("staging.enter.careers", timeout=5)
    context = Mock()
    conn._context = context
    conn.connect()
    connect.assert_called_once_with(("3.26.28.4", 443), timeout=5)
    context.wrap_socket.assert_called_once_with(raw, server_hostname="staging.enter.careers")


@pytest.mark.parametrize("healthy", [True, False])
@pytest.mark.parametrize("publish_fails", [True, False])
def test_handler_metric_and_redaction(probe, monkeypatch, capsys, healthy, publish_fails):
    import boto3

    module, scope = probe
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    check = Mock(side_effect=lambda path, kind: healthy if kind == "readiness" else True)
    monkeypatch.setitem(scope, "check_endpoint", check)
    client = Mock()
    if publish_fails:
        client.put_metric_data.side_effect = RuntimeError("SECRET provider response")
    monkeypatch.setattr(boto3, "client", Mock(return_value=client))
    result = module.handler({"url": "http://169.254.169.254/SECRET"}, None)
    assert result["metric_published"] is not publish_fails
    args = client.put_metric_data.call_args.kwargs
    assert args["Namespace"] == "ENTER/PublicAvailability"
    assert args["MetricData"][0]["Value"] == int(healthy)
    assert check.call_count == 2
    assert "SECRET" not in capsys.readouterr().out


def test_wrong_region_no_requests(probe, monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    check = Mock()
    monkeypatch.setitem(probe[1], "check_endpoint", check)
    assert probe[0].handler({}, None)["reason"] == "configuration"
    check.assert_not_called()


def test_infrastructure_safe_defaults_and_iam():
    path = ROOT / "deploy/prepare_public_monitor.py"
    scope = {"__name__": "synthetic_template", "__file__": str(path)}
    exec(compile(path.read_text(), str(path), "exec"), scope)
    docs = scope["documents"]()
    resources = docs["template.json"]["Resources"]
    assert resources["Schedule"]["Properties"]["State"] == "DISABLED"
    alarm = resources["AvailabilityAlarm"]["Properties"]
    assert alarm["TreatMissingData"] == "breaching"
    assert alarm["ActionsEnabled"] is False
    assert alarm["AlarmActions"] == alarm["OKActions"] == [scope["TOPIC"]]
    assert alarm["DatapointsToAlarm"] == alarm["EvaluationPeriods"] == 2
    assert "VpcConfig" not in resources["Probe"]["Properties"]
    assert "AWS::SNS::TopicPolicy" not in str(resources)
    permissions = docs["runtime-policy.json"]["Statement"]
    assert permissions[0]["Condition"]["StringEquals"]["cloudwatch:namespace"] == (
        "ENTER/PublicAvailability"
    )
    assert docs["scheduler-policy.json"]["Statement"][0]["Resource"] == scope["FUNCTION"]
    assert (
        docs["scheduler-trust.json"]["Statement"][0]["Condition"]["StringEquals"]["aws:SourceArn"]
        == scope["GROUP"]
    )
    assert not any(word in str(permissions) for word in ["s3:", "ec2:", "sns:", "sqs:"])


def test_artifact_checksums_and_no_overwrite(tmp_path):
    target = tmp_path / "artifacts"
    args = [sys.executable, str(ROOT / "deploy/prepare_public_monitor.py"), "--output", str(target)]
    subprocess.run(args, check=True, capture_output=True)
    for line in (target / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
        json.loads((target / name).read_text())
    template = json.loads((target / "template.json").read_text())
    assert (
        template["Resources"]["Probe"]["Properties"]["Code"]["ZipFile"]
        == (ROOT / "deploy/public_https_monitor.py").read_text()
    )
    assert subprocess.run(args, capture_output=True).returncode != 0


def test_installation_script_closed_without_approval():
    env = dict(os.environ, ENTER_APPROVE_MONITOR_CHANGE_SET="")
    result = subprocess.run(
        ["bash", str(ROOT / "deploy/public_monitor_change_set.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Approval gate closed; no AWS requests made." in result.stderr


def test_failure_then_recovery_metrics(probe, monkeypatch):
    import boto3

    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    client = Mock()
    monkeypatch.setattr(boto3, "client", Mock(return_value=client))
    for healthy in [True, False, False, True]:
        monkeypatch.setitem(probe[1], "check_endpoint", lambda *args, value=healthy: value)
        probe[0].handler({}, None)
    assert [
        call.kwargs["MetricData"][0]["Value"] for call in client.put_metric_data.call_args_list
    ] == [1, 0, 0, 1]
