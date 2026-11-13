import math
import json
import subprocess
from types import SimpleNamespace

import pytest

from chaos_lab import gate


def summary(success=1, dropped=0):
    return {"round": "R1", "profile": {"fixed": True}, "expected_revision": "a"*40,
            "metrics": {"http_reqs": {"values": {"count": 100}},
                        "flow_complete": {"values": {"rate": success}},
                        "dropped_iterations": {"values": {"count": dropped}}}}


@pytest.mark.parametrize("success,dropped,passed", [(1,0,True),(.99,0,True),(.98,0,False),(0,0,False),(1,1,False)])
def test_fast_failures_and_unserved_load_cannot_pass(success, dropped, passed):
    assert gate.evaluate_k6(summary(success,dropped), {"fixed":True}, "a"*40,"R1")["passed"] is passed


@pytest.mark.parametrize("field,value", [("round","R0"),("profile",{}),("expected_revision","b"*40)])
def test_evidence_requires_identical_instrument_and_revision(field,value):
    data = summary()
    data[field] = value
    with pytest.raises(ValueError):
        gate.evaluate_k6(data,{"fixed":True},"a"*40,"R1")


@pytest.mark.parametrize("value", [math.nan,math.inf,-1,2,True])
def test_invalid_rates_never_pass(value):
    with pytest.raises(ValueError):
        gate.evaluate_k6(summary(value),{"fixed":True},"a"*40,"R1")


def test_unconfigured_gate_never_launches_load_or_contacts_peers(monkeypatch):
    monkeypatch.setattr(gate.subprocess,"Popen",lambda *a,**kw: pytest.fail("Load started without scope"))
    monkeypatch.setattr(gate,"check_group",lambda *a: pytest.fail("Peer called without scope"))
    with pytest.raises(ValueError,match="Missing experiment configuration"):
        gate.run({})


def test_controller_timeout_still_cleans_fault_and_keeps_failure_evidence(monkeypatch,tmp_path):
    profile = tmp_path/"chaos/load/profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text('{"fixed":true}')
    monkeypatch.setattr(gate,"__file__",str(tmp_path/"chaos_lab/gate.py"))
    config = {"run_id":"b"*32,"round":"R0","max_p95_seconds":"1"}
    monkeypatch.setattr(gate,"experiment_configuration",lambda env: config)
    monkeypatch.setattr(gate,"check_group",lambda env: {"status":"verified"})
    clock = iter(range(0,1000,31))
    monkeypatch.setattr(gate.time,"monotonic",lambda: next(clock))
    monkeypatch.setattr(gate.providers,"flow_snapshot",lambda c: {"requests":300,"success_rate":1,"p95_seconds":.1,"max_p95_seconds":1})
    cleaned = []
    monkeypatch.setattr(gate.providers,"remove_latency",lambda c: cleaned.append(c["run_id"]))
    process = SimpleNamespace(poll=lambda: None,wait=lambda **kwargs: 0)
    monkeypatch.setattr(gate.subprocess,"Popen",lambda *args,**kwargs: process)
    def run(arguments,**kwargs):
        if arguments[0]=="docker":
            return SimpleNamespace(returncode=0)
        raise subprocess.TimeoutExpired(arguments,110)
    monkeypatch.setattr(gate.subprocess,"run",run)
    assert not gate.run({"EXPECTED_APP_REVISION":"a"*40})
    report = json.loads((tmp_path/"chaos/results"/config["run_id"]/"gate-report.json").read_text())
    assert cleaned == [config["run_id"]]
    assert report["rollback_verified"] and report["recovery_verified"]
    assert "TimeoutExpired" in report["failure_reason"]
