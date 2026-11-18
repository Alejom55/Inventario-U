"""Fail-closed gate for the group's explicitly accepted security experiment scope."""
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def scope_digest(rules):
    content={k:v for k,v in rules.items() if k not in ('participants','acceptance_note','owner_authorization')}
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def validate_scope(path,now=None):
    path=Path(path).resolve();rules=json.loads(path.read_text(encoding='utf-8'))
    now=now or datetime.now(timezone.utc)
    if rules.get('schema_version')!=1 or rules.get('experiment')!='E1':raise ValueError('Expected E1 rules of engagement')
    if rules.get('synthetic_only') is not True:raise ValueError('Only synthetic data are authorized')
    participants=rules.get('participants',[])
    names=set();digest=scope_digest(rules)
    mode=rules.get('authorization_mode','group')
    if mode=='owner_isolated_lab':
        owner=rules.get('owner_authorization',{})
        if participants or rules.get('isolated_lab') is not True or rules.get('evidence_class')!='owner_authorized_aws_lab':
            raise ValueError('Owner authorization is limited to a separate lab, not a group acceptance')
        if not owner.get('name','').strip() or owner.get('accepted') is not True or owner.get('source')!='direct_user_request':
            raise ValueError('Explicit owner authorization is required')
        if owner.get('accepted_scope_sha256')!=digest:raise ValueError('The accepted scope or window changed; owner authorization must be renewed')
        accepted=datetime.fromisoformat(owner['accepted_at_utc'].replace('Z','+00:00'))
        if accepted.tzinfo is None or accepted>now:raise ValueError('Owner authorization must precede execution')
        api=urlsplit(rules.get('api_origin',''));prom=urlsplit(rules.get('prometheus_origin',''))
        if not api.hostname or not api.hostname.startswith('e1.') or api.hostname!=prom.hostname:
            raise ValueError('Owner lab must use its separate E1 host and monitoring origin')
    elif mode!='group':raise ValueError('Unsupported experiment authorization mode')
    elif len(participants)!=3:raise ValueError('Three personal acceptances are required before cloud execution')
    for person in participants:
        name=person.get('name','').strip()
        if not name or name.casefold() in names or person.get('accepted') is not True:raise ValueError('Missing or duplicate participant acceptance')
        names.add(name.casefold())
        if person.get('accepted_scope_sha256')!=digest:raise ValueError('The accepted scope or window changed; acceptance must be renewed')
        signed=(path.parent/person['signed_pdf']).resolve()
        if not signed.is_relative_to(path.parent) or not signed.is_file():raise ValueError('Signed PDF must be within the private rules folder')
        content=signed.read_bytes()
        if not content.startswith(b'%PDF-') or hashlib.sha256(content).hexdigest()!=person.get('sha256'):
            raise ValueError('Signed PDF is missing or its digest changed')
        # This checks acceptance records and file integrity, not handwriting authenticity.
        accepted=datetime.fromisoformat(person['accepted_at_utc'].replace('Z','+00:00'))
        if accepted.tzinfo is None or accepted>now:raise ValueError('Acceptance must precede execution')
    start=datetime.fromisoformat(rules['window_start_utc'].replace('Z','+00:00'))
    end=datetime.fromisoformat(rules['window_end_utc'].replace('Z','+00:00'))
    if start.tzinfo is None or end.tzinfo is None or not start<=now<end-timedelta(seconds=90):
        raise ValueError('Outside the accepted window or insufficient time for observation and rollback')
    for field in ('api_origin','prometheus_origin'):
        value=rules[field];parsed=urlsplit(value)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443):
            raise ValueError('Only explicit HTTPS endpoints without credentials are allowed')
        if field=='api_origin' and parsed.path not in ('','/'):
            raise ValueError('API scope must name one origin, not a path prefix')
    if rules['provider']!='aws' or not re.fullmatch('[0-9]{12}',rules['account_id']) or not re.fullmatch('i-[a-f0-9]{17}',rules['instance_id']):
        raise ValueError('Expected an explicitly owned AWS account and instance')
    if not re.fullmatch('[a-f0-9]{40}',rules['application_revision']):raise ValueError('An immutable deployed revision is required')
    if rules.get('allowed_paths')!=['/api/v2/skus','/api/v2/skus/{id}','/api/v2/health','/api/v2/admin/security-result'] or rules.get('allowed_methods')!=['GET','POST','DELETE']:
        raise ValueError('Scope cannot grant other routes or operations')
    expected={'maximum_requests':100,'maximum_requests_per_second':2,'normal_requests':10,'adverse_requests':10,'observation_seconds':30,'containment_guardrail_seconds':5}
    if any(rules.get(k)!=v for k,v in expected.items()) or rules.get('objective')!={'name':'mttd_seconds','maximum':30}:
        raise ValueError('The declared E1 method must be identical in both rounds')
    if not rules.get('rollback') or rules.get('stop_file')!='security/runtime/STOP':raise ValueError('Stop switch and rollback are required')
    rules['scope_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return rules
