"""Prepare private lab material without starting services or executing a game day."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shutil

from .identity_tokens import create_keypair,issue
from .scope import scope_digest

ROOT=Path(__file__).resolve().parents[1]


def refresh_honeytoken(folder):
    folder=Path(folder)
    path=folder/'credentials.json';values=json.loads(path.read_text())
    honey=issue(values['issuer_private_key'],subject='unused-decoy-agent',ttl=300)
    digest=hashlib.sha256(honey.encode()).hexdigest()
    environments={}
    for current in ('R0','R1'):
        env=folder/(current+'.env')
        lines=env.read_text().splitlines()
        if sum(line.startswith('SECURITY_HONEYTOKEN_SHA256=') for line in lines)!=1:
            raise ValueError('Expected exactly one decoy hash in each round environment')
        environments[env]='\n'.join('SECURITY_HONEYTOKEN_SHA256='+digest if line.startswith('SECURITY_HONEYTOKEN_SHA256=') else line for line in lines)+'\n'
    values['honey_token']=honey
    for env,content in environments.items():env.write_text(content)
    path.write_text(json.dumps(values,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-honeytoken',action='store_true')
    args=parser.parse_args()
    folder=ROOT/'security/runtime';folder.mkdir(parents=True,exist_ok=True)
    if args.refresh_honeytoken:
        refresh_honeytoken(folder)
        print('Private decoy refreshed for 300 seconds. Reload the R1 process before use; issuer and other credentials unchanged.')
        return
    if (folder/'credentials.json').exists():raise ValueError('Private material already exists; do not silently rotate it')
    private,public=create_keypair(folder)
    values={'legacy_key':secrets.token_hex(32),'metrics_token':secrets.token_hex(32),'results_key':secrets.token_hex(32),
        'issuer_private_key':str(private.resolve()),'grafana_password':secrets.token_hex(24)}
    honey=issue(private,subject='unused-decoy-agent',ttl=300)
    values['honey_token']=honey
    (folder/'credentials.json').write_text(json.dumps(values,indent=2)+'\n')
    common={'TEAM_API_KEY':values['legacy_key'],'METRICS_BEARER_TOKEN':values['metrics_token'],
        'SECURITY_JWT_PUBLIC_KEY_FILE':'/run/identity/issuer-public.pem',
        'SECURITY_ALLOWED_SUBJECTS':'coordinator-demo,security-operator',
        'SECURITY_HONEYTOKEN_SHA256':hashlib.sha256(honey.encode()).hexdigest(),
        'RESOURCE_ADMIN_KEY':values['results_key'],'GRAFANA_ADMIN_PASSWORD':values['grafana_password'],'POSTGRES_PASSWORD':secrets.token_hex(32)}
    for current,mode in [('R0','legacy'),('R1','workload')]:
        environment={**common,'CHAOS_ROUND':current,'SECURITY_AUTH_MODE':mode}
        (folder/(current+'.env')).write_text(''.join(k+'='+v+'\n' for k,v in environment.items()))
    rules=folder/'rules-of-engagement.json'
    if not rules.exists():shutil.copyfile(ROOT/'security/rules-of-engagement.example.json',rules)
    for path in folder.iterdir():
        if path.is_file():path.chmod(0o600)
    token_path=folder/'metrics-token';token_path.write_text(values['metrics_token']);token_path.chmod(0o644)
    print('Private lab material generated. No services started; no signatures or cloud evidence generated.')
    print('Complete the exact scope, then obtain three personal acceptances before running.')
    print('Current incomplete scope digest:',scope_digest(json.loads(rules.read_text())))


if __name__=='__main__':main()
