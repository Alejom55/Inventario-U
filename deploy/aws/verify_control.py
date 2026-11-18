"""Read-only verification of the owned practice's native AWS protections."""
from datetime import datetime,timezone
import json
from pathlib import Path

from deploy.aws.launch import RUNTIME,REGION,PROJECT,session_clients,validate_free_account


def main():
    state=json.loads((RUNTIME/'deployment.json').read_text())
    clients=session_clients();ec2=clients['ec2']
    free=validate_free_account(clients['freetier'].get_account_plan_state())
    row=ec2.describe_instances(InstanceIds=[state['instance_id']])['Reservations'][0]['Instances'][0]
    assert {tag['Key']:tag['Value'] for tag in row['Tags']}['Project']==PROJECT
    assert row['InstanceType']=='t3.small' and row['State']['Name']=='running'
    assert row['MetadataOptions']['HttpTokens']=='required'
    disk=row['BlockDeviceMappings'][0]['Ebs'];assert disk['DeleteOnTermination']
    volume=ec2.describe_volumes(VolumeIds=[disk['VolumeId']])['Volumes'][0]
    assert volume['Encrypted'] and volume['VolumeType']=='gp3' and volume['Size']==8
    behavior=ec2.describe_instance_attribute(InstanceId=state['instance_id'],Attribute='instanceInitiatedShutdownBehavior')
    assert behavior['InstanceInitiatedShutdownBehavior']['Value']=='terminate'
    credits=ec2.describe_instance_credit_specifications(InstanceIds=[state['instance_id']])['InstanceCreditSpecifications'][0]
    assert credits['CpuCredits']=='standard'
    schedule=clients['scheduler'].get_schedule(Name=state['schedule_name'])
    assert schedule['State']=='ENABLED' and schedule['FlexibleTimeWindow']['Mode']=='OFF'
    assert schedule['ActionAfterCompletion']=='DELETE'
    assert schedule['Target']['Arn']=='arn:aws:scheduler:::aws-sdk:ec2:terminateInstances'
    assert json.loads(schedule['Target']['Input'])=={'InstanceIds':[state['instance_id']]}
    expected=datetime.fromisoformat(state['deadline_utc']).strftime('at(%Y-%m-%dT%H:%M:%S)')
    assert schedule['ScheduleExpression']==expected
    policy=clients['iam'].get_role_policy(RoleName=state['scheduler_role'],PolicyName='terminate-only-this-instance')['PolicyDocument']
    assert policy['Statement']==[{'Effect':'Allow','Action':'ec2:TerminateInstances',
        'Resource':f"arn:aws:ec2:{REGION}:{state['account']}:instance/{state['instance_id']}"}]
    group=ec2.describe_security_groups(GroupIds=[state['security_group_id']])['SecurityGroups'][0]
    ports={permission['FromPort']:[r['CidrIp'] for r in permission['IpRanges']] for permission in group['IpPermissions']}
    assert ports=={22:[state['plan']['ssh_cidr']],80:['0.0.0.0/0'],443:['0.0.0.0/0']}
    result={'verified_utc':datetime.now(timezone.utc).isoformat(),'provider':'aws',
        'instance_id':state['instance_id'],'free_account':free,'native_schedule_enabled':True,
        'deadline_utc':state['deadline_utc'],'scheduler_can_terminate_only_this_instance':True,
        'automatic_schedule_cleanup':True,'shutdown_behavior':'terminate','disk_encrypted':True,
        'disk_size_gib':8,'disk_delete_on_termination':True,'cpu_credits':'standard',
        'ssh_restricted_to_cloudshell':True,'only_public_ports':[80,443]}
    path=Path('docs/evidence/aws-control-verification.json')
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
