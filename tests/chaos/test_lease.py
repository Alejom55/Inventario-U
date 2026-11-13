import pytest

from chaos_lab import lease


@pytest.fixture
def scope(tmp_path):
    return {"toxiproxy_url": "http://127.0.0.1:8474", "proxy_name": "chaos-test", "expected_upstream": "peer:80", "run_id": "a"*32, "lease_db": str(tmp_path / "lease.sqlite3")}


def test_fresh_watchdog_required_and_other_lease_excluded(scope):
    with pytest.raises(ValueError, match="not initialized"):
        lease.arm(scope, now=100)
    lease.heartbeat(scope, now=100)
    lease.arm(scope, now=100)
    with pytest.raises(ValueError, match="Another experiment"):
        lease.arm({**scope, "run_id": "b"*32}, now=100)
    lease.release({**scope, "run_id": "b"*32})
    assert lease.expired(scope, now=200) == ["a"*32]
    lease.release(scope)
    assert lease.expired(scope, now=200) == []


@pytest.mark.parametrize("ready,at", [(False,100),(True,111),(True,99)])
def test_stale_unhealthy_or_future_heartbeat_cannot_arm(scope, ready, at):
    lease.heartbeat(scope, ready=ready, now=100)
    with pytest.raises(ValueError, match="heartbeat"):
        lease.arm(scope, now=at)


def test_scope_fingerprint_must_match_exact_proxy(scope):
    lease.heartbeat(scope, now=100)
    with pytest.raises(ValueError, match="heartbeat"):
        lease.arm({**scope,"expected_upstream":"another:80"}, now=100)


def test_expiry_survives_new_database_connection(scope):
    lease.heartbeat(scope, now=100)
    lease.arm(scope, ttl=2, now=100)
    assert lease.expired(dict(scope), now=101) == []
    assert lease.expired(dict(scope), now=102) == [scope["run_id"]]
