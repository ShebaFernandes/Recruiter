"""Off-host availability probe. No credentials, bodies or exception details in logs."""

import http.client
import ipaddress
import json
import os
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor

HOST = "staging.enter.careers"
REGION = "ap-southeast-2"
NAMESPACE = "ENTER/PublicAvailability"
TIMEOUT = 5
MAX_BODY = 65536


def public_address(host):
    # IPv4 deliberately matches the existing public endpoint. Never use a proxy,
    # local override, metadata endpoint, or a second unvalidated DNS resolution.
    records = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
    addresses = sorted({record[4][0] for record in records})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Non-public DNS result")
    return addresses[0]


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        address = public_address(self.host)
        raw = socket.create_connection((address, self.port), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def check_endpoint(path, kind):
    conn = None
    try:
        context = ssl.create_default_context()
        conn = PublicHTTPSConnection(HOST, timeout=TIMEOUT, context=context)
        conn.request("GET", path, headers={"User-Agent": "ENTER-Availability/1.0"})
        response = conn.getresponse()
        # Redirects are failures; never follow them to another host or private path.
        if response.status != 200:
            return False
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            return False
        content_type = response.getheader("Content-Type", "").lower()
        if kind == "frontend":
            return "text/html" in content_type and b'<div id="root"' in body
        if kind != "readiness" or "application/json" not in content_type:
            return False
        data = json.loads(body)
        return (
            isinstance(data, dict)
            and data.get("status") == "ready"
            and (data.get("database") == "ok")
        )
    except Exception:
        # Provider errors may contain URLs, headers or bodies. Never serialize them.
        return False
    finally:
        if conn is not None:
            conn.close()


def handler(event, context):
    # Ignore incoming event entirely: callers cannot inject URLs or credentials.
    if os.environ.get("AWS_REGION") != REGION:
        return {"metric_published": False, "reason": "configuration"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        frontend = pool.submit(check_endpoint, "/", "frontend")
        readiness = pool.submit(check_endpoint, "/api/v1/health/ready/", "readiness")
        results = {"frontend": frontend.result(), "readiness": readiness.result()}
    healthy = all(results.values())
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "cloudwatch",
            region_name=REGION,
            config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
        )
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{"MetricName": "Healthy", "Value": int(healthy), "Unit": "Count"}],
        )
    except Exception:
        print(json.dumps({"metric_published": False}))
        return {"metric_published": False}
    # Fixed keys and booleans only, never the event, HTTP body or raw exception.
    result = {"metric_published": True, "healthy": healthy, **results}
    print(json.dumps(result))
    return result
