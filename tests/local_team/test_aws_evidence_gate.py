from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.aws_evidence_gate import verify


def measured():
    return json.loads((Path(__file__).parents[2]/'docs/evidence/aws-cloud-results.json').read_text())


def test_archived_real_aws_rounds_pass():
    result=verify(measured())
    assert result['decision']=='PASS' and result['measured_r1']==100


def test_r1_below_threshold_fails_even_with_a_stale_success_flag():
    report=measured();r1=next(row for row in report['measurements'] if row['round']=='R1')
    r1.update(success_percent=98.99,objective_passed=True)
    with pytest.raises(ValueError,match='only decision metric'):verify(report)


def test_latency_does_not_become_a_second_decision_metric():
    report=measured();r1=next(row for row in report['measurements'] if row['round']=='R1')
    r1.update(p95_ms=900,guardrail_p95_passed=False)
    assert verify(report)['decision']=='PASS'


def test_comparison_requires_real_aws_and_same_profile():
    for mutation in ({'provider':'local'},{'same_profile':False}):
        report=deepcopy(measured());report.update(mutation)
        with pytest.raises(ValueError):verify(report)
