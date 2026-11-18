"""Run inside AWS CloudShell: inspect first, then launch one disposable practice."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

REGION='us-east-2'
INSTANCE_TYPE='t3.small'
RUNTIME=Path(__file__).resolve().parent/'runtime'
PROJECT='inventario-chaos-practice'


def validate_plan(price,revision):
    if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Expected immutable Git revision')
    if not 0<price<=0.04:raise ValueError('Unexpected hourly price')
    # Reserve $0.25 for traffic plus ample tax/headroom; no optional paid services.
    estimate=2*(price+0.005+8*0.08/730)+0.25
    if estimate>0.75:raise ValueError('Budget reserve insufficient')
    return round(estimate,4)


def validate_free_account(account):
    if account.get('accountPlanType')!='FREE' or account.get('accountPlanStatus')!='ACTIVE':
        raise ValueError('Only an ACTIVE FREE account is authorized; never upgrade the account')
    credits=account.get('accountPlanRemainingCredits',{})
    if credits.get('unit')!='USD' or float(credits.get('amount',0))<1:
        raise ValueError('Insufficient free credits for the protected practice')
    expiration=account['accountPlanExpirationDate']
    if isinstance(expiration,str):expiration=datetime.fromisoformat(expiration.replace('Z','+00:00'))
    if expiration<=datetime.now(timezone.utc)+timedelta(hours=2):
        raise ValueError('Free plan expires before the authorized window ends')
    return {'type':'FREE','status':'ACTIVE','remaining_credits_usd':float(credits['amount']),
        'expiration_utc':expiration.isoformat(),'maximum_out_of_pocket_usd':0}


def session_clients():
    import boto3
    session=boto3.Session(region_name=REGION)
    return {name:session.client(name,region_name='us-east-1' if name in ('pricing','freetier') else REGION)
            for name in ('ec2','ssm','sts','pricing','iam','scheduler','freetier')}


def plan(clients):
    ec2=clients['ec2']
    free=validate_free_account(clients['freetier'].get_account_plan_state())
    eligible=ec2.describe_instance_types(InstanceTypes=[INSTANCE_TYPE])['InstanceTypes'][0]['FreeTierEligible']
    if eligible is not True:raise ValueError('Instance is not Free Tier eligible')
    identity=clients['sts'].get_caller_identity()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    products=clients['pricing'].get_products(ServiceCode='AmazonEC2',Filters=[
        {'Type':'TERM_MATCH','Field':k,'Value':v} for k,v in {
            'instanceType':INSTANCE_TYPE,'location':'US East (Ohio)',
            'operatingSystem':'Linux','tenancy':'Shared','preInstalledSw':'NA',
            'capacitystatus':'Used'}.items()],MaxResults=10)
    prices=[]
    for raw in products['PriceList']:
        product=json.loads(raw)
        for term in product['terms']['OnDemand'].values():
            prices.extend(float(value['pricePerUnit']['USD']) for value in term['priceDimensions'].values() if value['unit']=='Hrs')
    if not prices:raise RuntimeError('Could not verify current compute price')
    price=max(prices)
    budget=validate_plan(price,revision)
    image=clients['ssm'].get_parameter(Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64')['Parameter']['Value']
    ami=ec2.describe_images(ImageIds=[image])['Images'][0]
    subnets=ec2.describe_subnets(Filters=[{'Name':'default-for-az','Values':['true']}])['Subnets']
    subnet=next(s for s in subnets if s['MapPublicIpOnLaunch'])
    existing=ec2.describe_instances(Filters=[{'Name':'tag:Project','Values':[PROJECT]},
        {'Name':'instance-state-name','Values':['pending','running','stopping','stopped']}])
    if any(row['Instances'] for row in existing['Reservations']):raise RuntimeError('An owned practice already exists; do not duplicate')
    address=urlopen('https://checkip.amazonaws.com',timeout=10).read().decode().strip()
    import ipaddress
    ipaddress.IPv4Address(address)
    result={'provider':'aws','region':REGION,'account':identity['Account'],'type':INSTANCE_TYPE,
        'hourly_compute_usd':price,'reserved_total_usd':budget,'maximum_credit_usage_usd':1,'hours':2,
        'billing_protection':free,'free_tier_eligible':eligible,
        'revision':revision,'ami':image,'root_device':ami['RootDeviceName'],
        'subnet':subnet['SubnetId'],'vpc':subnet['VpcId'],'ssh_cidr':address+'/32',
        'ports':{'22':'CloudShell current IPv4 only','80':'public ACME and HTTPS redirect','443':'authenticated API and Prometheus'},
        'cpu_credits':'standard; no surplus-credit charges','root_disk':'8 GiB encrypted gp3; delete on termination',
        'expiry':'systemd shutdown plus independent AWS Scheduler termination',
        'ephemeral_data':'synthetic data only; export evidence before deadline'}
    RUNTIME.mkdir(parents=True,exist_ok=True)
    (RUNTIME/'plan.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def apply(clients,expected):
    current=plan(clients)
    # Re-read the actual price and account immediately before creating anything.
    if any(current[k]!=expected[k] for k in ('account','revision','hourly_compute_usd','subnet','vpc','ssh_cidr')):
        raise RuntimeError('Plan changed; review before launching')
    ec2=clients['ec2'];iam=clients['iam'];scheduler=clients['scheduler']
    now=datetime.now(timezone.utc);deadline=now+timedelta(hours=2)
    name=PROJECT+'-'+now.strftime('%m%d%H%M%S')
    state={'name':name,'account':current['account'],'region':REGION,'deadline_utc':deadline.isoformat(),
        'application_revision':current['revision'],'plan':current}
    def save():(RUNTIME/'deployment.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    key=RUNTIME/'operator-key'
    if key.exists():raise RuntimeError('Refusing to overwrite an operator key')
    subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(key)],check=True,capture_output=True)
    group=None;instance=None
    try:
        tags=[{'Key':'Project','Value':PROJECT},{'Key':'Name','Value':name}]
        group=ec2.create_security_group(GroupName=name,Description='Disposable authenticated Inventario-U practice',VpcId=current['vpc'],TagSpecifications=[{'ResourceType':'security-group','Tags':tags}])['GroupId']
        state['security_group_id']=group;save()
        ec2.authorize_security_group_ingress(GroupId=group,IpPermissions=[
            {'IpProtocol':'tcp','FromPort':port,'ToPort':port,'IpRanges':[{'CidrIp':cidr}]}
            for port,cidr in ((22,current['ssh_cidr']),(80,'0.0.0.0/0'),(443,'0.0.0.0/0'))])
        ec2.import_key_pair(KeyName=name,PublicKeyMaterial=key.with_suffix('.pub').read_bytes(),TagSpecifications=[{'ResourceType':'key-pair','Tags':tags}])
        state['key_name']=name;save()
        user_data=(Path(__file__).parent/'bootstrap.sh').read_text().replace('__REVISION__',current['revision']).replace('__DEADLINE__',deadline.strftime('%Y-%m-%d %H:%M:%S UTC'))
        result=ec2.run_instances(ImageId=current['ami'],InstanceType=INSTANCE_TYPE,MinCount=1,MaxCount=1,KeyName=name,
            NetworkInterfaces=[{'DeviceIndex':0,'SubnetId':current['subnet'],'Groups':[group],'AssociatePublicIpAddress':True}],
            BlockDeviceMappings=[{'DeviceName':current['root_device'],'Ebs':{'VolumeSize':8,'VolumeType':'gp3','Encrypted':True,'DeleteOnTermination':True}}],
            CreditSpecification={'CpuCredits':'standard'},InstanceInitiatedShutdownBehavior='terminate',
            MetadataOptions={'HttpTokens':'required','HttpEndpoint':'enabled','HttpPutResponseHopLimit':1},
            Monitoring={'Enabled':False},UserData=user_data,
            TagSpecifications=[{'ResourceType':kind,'Tags':tags} for kind in ('instance','volume')])
        instance=result['Instances'][0]['InstanceId'];state['instance_id']=instance;save()
        role=iam.create_role(RoleName=name,AssumeRolePolicyDocument=json.dumps({'Version':'2012-10-17','Statement':[{
            'Effect':'Allow','Principal':{'Service':'scheduler.amazonaws.com'},'Action':'sts:AssumeRole',
            'Condition':{'StringEquals':{'aws:SourceAccount':current['account']}}}]}))['Role']
        state['scheduler_role']=name;save()
        iam.put_role_policy(RoleName=name,PolicyName='terminate-only-this-instance',PolicyDocument=json.dumps({
            'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':'ec2:TerminateInstances',
            'Resource':f"arn:aws:ec2:{REGION}:{current['account']}:instance/{instance}"}]}))
        import time
        for attempt in range(8):
            try:
                scheduler.create_schedule(Name=name,ScheduleExpression='at('+deadline.strftime('%Y-%m-%dT%H:%M:%S')+')',
                    ScheduleExpressionTimezone='UTC',FlexibleTimeWindow={'Mode':'OFF'},ActionAfterCompletion='DELETE',
                    Target={'Arn':'arn:aws:scheduler:::aws-sdk:ec2:terminateInstances','RoleArn':role['Arn'],
                        'Input':json.dumps({'InstanceIds':[instance]}),'RetryPolicy':{'MaximumRetryAttempts':0,'MaximumEventAgeInSeconds':60}})
                break
            except scheduler.exceptions.ValidationException:
                if attempt==7:raise
                time.sleep(3)
        state['schedule_name']=name;state['expiry_verified']=True;save()
        ec2.get_waiter('instance_running').wait(InstanceIds=[instance])
        row=ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
        state.update(public_ip=row['PublicIpAddress'],api_url='https://'+row['PublicIpAddress']+'.sslip.io',
            prometheus_url='https://'+row['PublicIpAddress']+'.sslip.io/prometheus')
        save();return state
    except Exception:
        # Failure before a verified independent expiry must not leave compute running.
        if instance:ec2.terminate_instances(InstanceIds=[instance])
        state['failed_closed']=True;save()
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('plan','apply'))
    args=parser.parse_args();clients=session_clients()
    if args.action=='plan':result=plan(clients)
    else:
        expected=json.loads((RUNTIME/'plan.json').read_text());result=apply(clients,expected)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
