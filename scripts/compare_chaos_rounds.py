"""Compare actual gate reports; missing, incomparable or unsuccessful R1 fail."""
import argparse
import json
import math
from pathlib import Path


def compare(r0,r1):
    if r0.get("round")!="R0" or r1.get("round")!="R1":
        raise ValueError("Provide R0 then R1")
    for name in ("profile_sha256","profile","fault","threshold","revision"):
        if not r0.get(name) or r0[name] != r1.get(name):
            raise ValueError("The two rounds differ or omit: "+name)
    if not r0.get("contracts",{}).get("group_fingerprint") or r0["contracts"]["group_fingerprint"] != r1.get("contracts",{}).get("group_fingerprint"):
        raise ValueError("URLs, routes or synthetic data changed between rounds")
    changes = {}
    for name in ("p95_seconds","success_rate","requests"):
        before,after = [report["fault_measurement"][name] for report in (r0,r1)]
        if not all(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 for value in (before,after)):
            raise ValueError("Missing or invalid measurements")
        changes[name] = {"R0":before,"R1":after,"variation_percent":100*(after-before)/before if before else None}
    r0_refuted = changes["requests"]["R0"] >= r0["threshold"].get("minimum_samples",100) and r0.get("chaos_toolkit_exit_code") is not None and r0.get("fault_measurement",{}).get("toxic_present") is True and not r0.get("passed") and (
        changes["p95_seconds"]["R0"] > r0["threshold"]["max_p95_seconds"] or changes["success_rate"]["R0"] < .99)
    verified = all(report.get("rollback_verified") and report.get("recovery_verified") for report in (r0,r1))
    return {"measurements":changes,"R0_refuted_by_measurement":r0_refuted,"R1_gate_passed":bool(r1.get("passed")),
            "both_reversals_and_recoveries_verified":verified,"ready":r0_refuted and bool(r1.get("passed")) and verified,
            "note":"Null variation means R0 was zero; infrastructure and the other two faults need separate evidence"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("r0",type=Path)
    parser.add_argument("r1",type=Path)
    args = parser.parse_args()
    report = compare(json.loads(args.r0.read_text(encoding="utf-8")),json.loads(args.r1.read_text(encoding="utf-8")))
    print(json.dumps(report,indent=2,allow_nan=False))
    raise SystemExit(0 if report["ready"] else 1)
