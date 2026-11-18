"""Validate archived AWS measurements; this gate does not inject the experiment."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re


def decision(report):
    value=report['mttd_seconds']
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=30:
        raise ValueError('R1 measured MTTD exceeds the sole 30-second objective or is missing')
    if not report['rollback_verified']:raise ValueError('R1 rollback was not verified')
    return True


def verify(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'SHA256.json').read_text())
    for name,expected in manifest.items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Evidence digest mismatch: '+name)
    summary=json.loads((folder/'summary.json').read_text())
    reports=[]
    for entry in summary['rounds']:
        execution=entry['execution_id']
        if not re.fullmatch('[a-f0-9]{32}',execution):raise ValueError('Invalid execution ID')
        path=folder/execution
        report=json.loads((path/'report.json').read_text());raw=json.loads((path/'raw.json').read_text())
        if hashlib.sha256((path/'raw.json').read_bytes()).hexdigest()!=report['raw_sha256']:raise ValueError('Raw report provenance changed')
        if report['evidence_class']!='owner_authorized_aws_lab' or report['provider']!='aws':raise ValueError('Wrong evidence classification')
        if report['instance_id']!=summary['instance_id'] or not report['rollback_verified'] or raw['cleanup_error_type'] is not None:raise ValueError('Invalid deployment or cleanup')
        normal=[row for row in raw['requests'] if row['kind']=='normal']
        adverse=[row for row in raw['requests'] if row['kind']=='adverse']
        if len(normal)!=10 or len(adverse)!=10 or any(row['status']!=200 for row in normal):raise ValueError('Profile or normal baseline mismatch')
        if not all(re.fullmatch('[a-f0-9]{32}',row['trace_id']) for row in raw['requests']):raise ValueError('Missing trace provenance')
        expected=(201,) if report['round']=='R0' else (401,403)
        if any(row['status'] not in expected for row in adverse):raise ValueError('Adverse responses contradict the measured scenario')
        if report['request_count']>100 or not 30<=report['observation_seconds']<35:raise ValueError('Load bounds changed')
        if report['round']=='R1':
            decision(report)
            alert=report['alert_evidence'];signals=alert['prometheus_result']
            if not signals or any(s['metric'].get('alertstate')!='firing' or s['metric'].get('round')!='R1' for s in signals):raise ValueError('Missing native R1 alert')
            elapsed=(datetime.fromisoformat(alert['observed_utc'])-datetime.fromisoformat(report['injected_utc'])).total_seconds()
            if abs(elapsed-report['mttd_seconds'])>1:raise ValueError('UTC evidence contradicts the measured detection time')
        reports.append(report)
    if len(reports)!=2 or {r['round'] for r in reports}!={'R0','R1'} or reports[0]['method']!=reports[1]['method']:raise ValueError('Two comparable rounds are required')
    return {'decision':'PASS','objective':'R1 measured MTTD <=30 seconds',
        'classification':'owner_authorized_aws_lab','rounds':[{'round':r['round'],'execution_id':r['execution_id'],
            'mttd_seconds':r['mttd_seconds'],'mttc_seconds':r['mttc_seconds'],'rollback_verified':r['rollback_verified']} for r in reports]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=Path('docs/evidence/ciber-e1-aws'))
    args=parser.parse_args();print(json.dumps(verify(args.folder),indent=2))


if __name__=='__main__':main()
