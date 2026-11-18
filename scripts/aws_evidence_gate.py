"""Decide the AWS fault-c outcome from measured success, never a supplied pass flag."""
import json
import math
from pathlib import Path


def verify(report):
    if report.get('provider')!='aws' or report.get('same_profile') is not True:
        raise ValueError('Expected real AWS measurements with one shared load profile')
    measurements=report['measurements'];rows={row['round']:row for row in measurements}
    if len(measurements)!=3 or set(rows)!={'BASELINE','R0','R1'}:
        raise ValueError('Exactly BASELINE, R0 and R1 are required')
    for row in rows.values():
        if row['profile']!=rows['BASELINE']['profile'] or row['rollback_verified'] is not True:
            raise ValueError('Changed profile or unverified rollback')
        if row['execution_id']!=report['execution_id'] or row['revision']!=report['application_revision']:
            raise ValueError('Execution or deployed revision mismatch')
        if row['deployment']['provider']!='aws' or row['deployment']['instance_id']!=report['instance_id']:
            raise ValueError('Measurements do not identify the same AWS instance')
        value=row['success_percent']
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:
            raise ValueError('Invalid measured success percentage')
    if rows['BASELINE']['success_percent']<99:raise ValueError('Baseline success is below 99%')
    if rows['R0']['success_percent']>=99 or rows['R0']['fault']['injection']['admitted']!=6:
        raise ValueError('R0 does not demonstrate unprotected exhaustion')
    if rows['R1']['fault']['injection']['admitted']!=4:
        raise ValueError('R1 does not demonstrate bounded admission')
    if rows['R1']['success_percent']<99:raise ValueError('R1 fails the only decision metric: success >=99%')
    return {'decision':'PASS','metric':'success_percent','threshold':99,'measured_r1':rows['R1']['success_percent'],
        'latency_role':'diagnostic only; no second decision threshold'}


if __name__=='__main__':
    path=Path('docs/evidence/aws-cloud-results.json')
    print(json.dumps(verify(json.loads(path.read_text()))))
