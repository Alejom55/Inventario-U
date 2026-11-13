from copy import deepcopy

import pytest

from scripts.compare_chaos_rounds import compare


def reports():
    base = {"profile_sha256":"profile","profile":{"fixed":True},"fault":{"latency_ms":1500},
            "threshold":{"max_p95_seconds":1},"revision":"a"*40,"contracts":{"group_fingerprint":"group"},
            "chaos_toolkit_exit_code":1,"rollback_verified":True,"recovery_verified":True}
    r0 = {**deepcopy(base),"round":"R0","passed":False,"fault_measurement":{"toxic_present":True,"p95_seconds":1.6,"success_rate":1,"requests":600}}
    r1 = {**deepcopy(base),"round":"R1","passed":True,"fault_measurement":{"toxic_present":True,"p95_seconds":.4,"success_rate":1,"requests":600}}
    return r0,r1


def test_real_refutation_and_recovery_required():
    r0,r1 = reports()
    result = compare(r0,r1)
    assert result["ready"] and result["measurements"]["p95_seconds"]["variation_percent"] == pytest.approx(-75)
    r1["recovery_verified"] = False
    assert not compare(r0,r1)["ready"]


def test_an_operational_failure_is_not_a_refuted_hypothesis():
    r0,r1 = reports()
    r0["fault_measurement"]["p95_seconds"] = .6
    assert not compare(r0,r1)["R0_refuted_by_measurement"]


@pytest.mark.parametrize("field", ["profile","threshold","revision","fault"])
def test_different_rounds_cannot_be_compared(field):
    r0,r1 = reports()
    r1[field] = "changed"
    with pytest.raises(ValueError):
        compare(r0,r1)


def test_zero_baseline_is_not_an_infinite_percentage():
    r0,r1 = reports()
    r0["fault_measurement"]["success_rate"] = 0
    assert compare(r0,r1)["measurements"]["success_rate"]["variation_percent"] is None
