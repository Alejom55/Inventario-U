"""CloudShell-only restoration of service credentials before announcing a replacement URL."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess

from deploy.aws.launch import RUNTIME

NAMES=('TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN')


def previous_credentials(path):
    values=json.loads(Path(path).read_text())
    if any(not isinstance(values.get(name),str) or not re.fullmatch('[a-f0-9]{64}',values[name]) for name in NAMES):
        raise ValueError('Expected the three existing service secrets; no values were printed')
    return {name:values[name] for name in NAMES}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--previous',type=Path,required=True)
    args=parser.parse_args();values=previous_credentials(args.previous)
    state=json.loads((RUNTIME/'deployment.json').read_text())
    if state.get('expiry_verified') is not True:raise ValueError('Independent expiry must be verified first')
    ssh=['ssh','-o','ConnectTimeout=7','-o','StrictHostKeyChecking=accept-new','-i',str(RUNTIME/'operator-key'),'ec2-user@'+state['public_ip']]
    subprocess.run(ssh+['sudo test -f /opt/inventario/BOOTSTRAP_READY'],check=True)
    remote='''import json,re,sys
from pathlib import Path
incoming=json.load(sys.stdin)
folder=Path('/opt/inventario/deploy/aws')
environment=folder/'.env';text=environment.read_text()
current=json.loads((folder/'runtime/credentials.json').read_text())
for name,value in incoming.items():
    assert name in ('TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN')
    assert re.fullmatch('[a-f0-9]{64}',value)
    assert len(re.findall('^'+name+'=.*$',text,re.M))==1
    text=re.sub('^'+name+'=.*$',name+'='+value,text,flags=re.M)
    current[name]=value
temporary=folder/'.env.next';temporary.write_text(text);temporary.chmod(0o600);temporary.replace(environment)
credentials=folder/'runtime/credentials.json';credentials.write_text(json.dumps(current,indent=2)+'\\n');credentials.chmod(0o600)
metrics=folder/'runtime/metrics-token';metrics.write_text(incoming['METRICS_BEARER_TOKEN']);metrics.chmod(0o644)
print('Three service credentials restored without disclosure; database password preserved')
'''
    subprocess.run(ssh+['sudo python3 -c '+shlex.quote(remote)],input=json.dumps(values),text=True,check=True)
    subprocess.run(ssh+['sudo docker compose --env-file /opt/inventario/deploy/aws/.env -f /opt/inventario/deploy/aws/compose.yml up -d --no-deps --force-recreate api prometheus gateway'],check=True)
    values.update(APP_REVISION=state['application_revision'],AWS_INSTANCE_ID=state['instance_id'],PUBLIC_HOST=state['public_ip']+'.sslip.io')
    path=RUNTIME/'credentials.json';path.write_text(json.dumps(values,indent=2)+'\n');path.chmod(0o600)
    print('Replacement service credentials restored. Verify HTTPS before announcing the new URL.')


if __name__=='__main__':main()
