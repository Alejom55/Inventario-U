"""Inspect, resume or suspend only this new Render Free practice."""
import argparse
from datetime import datetime,timedelta,timezone
import json

from deploy.render.free import api,read,write
from scripts.render_free_guard import start,suspend


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','start','stop'))
    args=parser.parse_args();state=read('deployment.json')
    if args.action=='stop':
        suspend();print('Only the two new Free web services suspended; synthetic Free database retained')
    elif args.action=='start':
        for key in ('api_service_id','prometheus_service_id'):
            service=api('GET','/services/'+state[key]);assert service['serviceDetails']['plan']=='free'
            if service.get('suspended')=='suspended':api('POST','/services/'+state[key]+'/resume')
        guard=read('guard.json',{})
        guard['deadline_utc']=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat();write('guard.json',guard)
        start(datetime.fromisoformat(guard['deadline_utc']))
        print('Practice resumed; allow cold start. Two-hour suspension scheduled; URLs unchanged')
    else:
        for key in ('api_service_id','prometheus_service_id'):
            service=api('GET','/services/'+state[key]);print(json.dumps({
                'name':service['name'],'plan':service['serviceDetails']['plan'],
                'suspended':service.get('suspended'),'url':service['serviceDetails']['url']}))
        print(json.dumps({'guard':read('guard.json',{})}))


if __name__=='__main__':main()
