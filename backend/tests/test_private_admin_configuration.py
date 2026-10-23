from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_public_admin_stays_blocked_and_private_listener_is_loopback_only():
    caddy = (ROOT / "deploy" / "Caddyfile").read_text()
    compose = (ROOT / "compose.production.yaml").read_text()

    assert 'handle /admin* {\n        respond "Not found" 404' in caddy
    assert "https://{$ENTER_DOMAIN}:8443" in caddy
    assert "handle /admin* {" in caddy
    assert "127.0.0.1:8443:8443" in compose
    assert "0.0.0.0:8443:8443" not in compose
    assert "PRIVATE_ADMIN_ORIGIN: https://${ENTER_DOMAIN}:8443" in compose


def test_private_listener_only_routes_admin():
    caddy = (ROOT / "deploy" / "Caddyfile").read_text()
    private_listener = caddy.split("https://{$ENTER_DOMAIN}:8443", maxsplit=1)[1]

    assert "reverse_proxy backend:8000" in private_listener
    assert 'respond "Not found" 404' in private_listener
    assert "handle /static/admin/*" in private_listener
    assert "handle /api/*" not in private_listener
