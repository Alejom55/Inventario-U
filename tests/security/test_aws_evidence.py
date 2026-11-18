import json
from pathlib import Path
import pytest
from security.verify_aws_evidence import decision,verify


def test_archived_cloud_rounds_are_consistent_and_pass_numeric_gate():
    root=Path(__file__).parents[2]/'docs/evidence/ciber-e1-aws'
    assert verify(root)['decision']=='PASS'


@pytest.mark.parametrize('value',[None,30.001,float('nan')])
def test_claimed_success_cannot_override_measured_objective(value):
    with pytest.raises(ValueError,match='MTTD'):
        decision({'mttd_seconds':value,'rollback_verified':True,'objective':{'passed':True}})
