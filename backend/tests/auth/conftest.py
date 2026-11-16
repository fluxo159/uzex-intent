import pytest
from fastapi.testclient import TestClient

ADMIN = "admin-secret-for-tests-0123456789"
CODES = ["JURY2035", "MENTOR77"]

@pytest.fixture()
def protected(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_ENFORCE", "1")
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("AUTH_SECRET", "test-secret-" + "x" * 20)
    monkeypatch.setenv("JURY_CODES", ",".join(CODES))
    monkeypatch.setenv("ACCESS_LOG", str(tmp_path / "access.log"))
    monkeypatch.setenv("AUTOCLOSE_MIN", "0")
    monkeypatch.delenv("ENV", raising=False)
    from app.demo import scenario
    from app.middleware import accesslog, cache, ratelimit
    ratelimit.reset()
    cache.clear()
    _drop_log_handlers(accesslog)
    accesslog.reset()
    scenario.reset(1)
    yield tmp_path
    ratelimit.reset()
    cache.clear()
    _drop_log_handlers(accesslog)
    scenario.reset(1)

def _drop_log_handlers(accesslog) -> None:
    lg = accesslog.logger()
    for h in list(lg.handlers):
        lg.removeHandler(h)
        h.close()
    accesslog._log = None

@pytest.fixture()
def client(protected):
    from app.main import app
    return TestClient(app)

def jury_client(code: str = CODES[0], ip: str | None = None) -> TestClient:
    from app.main import app
    c = TestClient(app, headers={"X-Real-IP": ip} if ip else None)
    r = c.post("/auth/code", json={"code": code})
    assert r.status_code == 200, r.text
    return c

def admin_headers() -> dict:
    return {"X-Admin-Token": ADMIN}
