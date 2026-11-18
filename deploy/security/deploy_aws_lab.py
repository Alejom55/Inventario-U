"""Deploy only the isolated E1 services on the existing, authorized AWS VM."""
import base64
import json
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'security/runtime'
AWS=ROOT/'deploy/aws/runtime'
HOST='3.151.219.131'
INSTANCE='i-094c00455c9ac62ba'
REVISION='c2ee1dc85710563768a844a671bc61b2d1f69ead'
IMAGE='sha256:d341ab3eac40b847d0ffd81b0b458b304a587b7d6f51c4c499b90eb2fb431158'


def ssh_options():
    return ['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(AWS/'e1-known-hosts'),
        '-o','ConnectTimeout=8','-i',str(AWS/'e1-operator-key')]


def remote(code):
    return subprocess.run(['ssh',*ssh_options(),'ec2-user@'+HOST,'sudo python3 -'],input=code,text=True,check=True,capture_output=True)


def main():
    credentials=RUNTIME/'credentials.json'
    values=json.loads(credentials.read_text(encoding='utf-8'))
    shared=json.loads((AWS/'credentials.json').read_text(encoding='utf-8'))
    assert values['legacy_key']!=shared['TEAM_API_KEY'],'Never experiment with the shared business key'
    # The gateway authenticates queries; the isolated API keeps its own scrape token.
    values['prometheus_token']=shared['METRICS_BEARER_TOKEN']
    credentials.write_text(json.dumps(values,indent=2)+'\n',encoding='utf-8')
    for current in ('R0','R1'):
        path=RUNTIME/(current+'.env')
        env=dict(line.split('=',1) for line in path.read_text(encoding='utf-8').splitlines() if '=' in line)
        env.update(APP_REVISION=REVISION,AWS_INSTANCE_ID=INSTANCE,SECURITY_API_IMAGE=IMAGE)
        path.write_text(''.join(k+'='+v+'\n' for k,v in env.items()),encoding='utf-8')
    standby=(RUNTIME/'R1.env').read_text(encoding='utf-8').replace('CHAOS_ROUND=R1\n','CHAOS_ROUND=none\n')
    (RUNTIME/'standby.env').write_text(standby,encoding='utf-8')
    files=['deploy/security/compose.aws.yml','deploy/security/prometheus.aws.yml','deploy/security/Caddyfile.aws',
        'security/detection/identity-alerts.yml','security/runtime/issuer-public.pem','security/runtime/metrics-token',
        'security/runtime/R0.env','security/runtime/R1.env','security/runtime/standby.env']
    archive=RUNTIME/'cloud-lab.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in files:tar.add(ROOT/name,arcname=name)
    subprocess.run(['scp',*ssh_options(),str(archive),'ec2-user@'+HOST+':/home/ec2-user/e1-lab-upload.tar.gz'],check=True)
    code=r'''
from pathlib import Path
import json,subprocess,tarfile,urllib.request
root=Path('/opt/inventario-e1');shared=Path('/opt/inventario')
def run(args):return subprocess.check_output(args,text=True).strip()
assert run(['git','-C',str(shared),'rev-parse','HEAD'])=='APPREVISION'
token=urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/api/token',method='PUT',headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'}),timeout=3).read().decode()
instance=urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/meta-data/instance-id',headers={'X-aws-ec2-metadata-token':token}),timeout=3).read().decode()
assert instance=='INSTANCEID'
assert run(['docker','image','inspect','APIIMAGE','--format','{{.Id}}'])=='APIIMAGE'
root.mkdir(mode=0o700,exist_ok=True)
with tarfile.open('/home/ec2-user/e1-lab-upload.tar.gz') as tar:
    for member in tar.getmembers():
        target=(root/member.name).resolve()
        assert member.isfile() and target.is_relative_to(root) and '..' not in Path(member.name).parts
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        target.write_bytes(tar.extractfile(member).read())
        target.chmod(0o600 if target.suffix=='.env' else 0o644)
compose=['docker','compose','--env-file',str(root/'security/runtime/standby.env'),'-f',str(root/'deploy/security/compose.aws.yml')]
subprocess.run(compose+['config','--quiet'],check=True)
subprocess.run(compose+['up','-d','--wait','--wait-timeout','100'],check=True)
gateway=run(['docker','compose','--env-file',str(shared/'deploy/aws/.env'),'-f',str(shared/'deploy/aws/compose.yml'),'ps','-q','gateway'])
path=shared/'deploy/aws/Caddyfile';before=path.read_text();backup=path.with_name('Caddyfile.before-e1')
if not backup.exists():backup.write_text(before)
try:
    block=(root/'deploy/security/Caddyfile.aws').read_text()
    if 'e1.3.151.219.131.sslip.io {' not in before:path.write_text(before+'\n'+block)
    subprocess.run(['docker','exec',gateway,'caddy','validate','--config','/etc/caddy/Caddyfile'],check=True)
    subprocess.run(['docker','exec',gateway,'caddy','reload','--force','--config','/etc/caddy/Caddyfile'],check=True)
except Exception:
    path.write_text(before)
    subprocess.run(['docker','exec',gateway,'caddy','reload','--force','--config','/etc/caddy/Caddyfile'],check=True)
    raise
print(json.dumps({'instance_id':instance,'api_url':'https://e1.3.151.219.131.sslip.io',
    'application_revision':'APPREVISION','application_image':'APIIMAGE','state':'standby',
    'identity_policy':'workload','round':'none','shared_service_restarted':False}))
'''.replace('APPREVISION',REVISION).replace('INSTANCEID',INSTANCE).replace('APIIMAGE',IMAGE)
    result=remote(code)
    print(result.stdout)
    deployment=json.loads(result.stdout.strip().splitlines()[-1])
    (RUNTIME/'cloud-deployment.json').write_text(json.dumps(deployment,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
