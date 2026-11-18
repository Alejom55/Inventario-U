"""Opt-in machine identity policy; legacy API keys remain the default until rollout."""
from dataclasses import dataclass
import hashlib
import hmac
import logging
import os
from pathlib import Path
import re
import time

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter,Gauge

from .observability import correlation_id,round_identity

logger=logging.getLogger('app.security_identity')
DECISIONS=Counter('inventory_security_identity_decisions_total','Machine identity authorization decisions',('round','decision','reason'))
DETECTIONS=Counter('inventory_security_identity_detections_total','Security detections, not ordinary business errors',('round','reason'))
LAST_DETECTION=Gauge('inventory_security_identity_last_detection_timestamp_seconds','UTC event time of the last identity detection',('round','reason'))
POLICY=Gauge('inventory_security_identity_policy','Configured machine identity policy',('mode',))


@dataclass(frozen=True)
class IdentityPolicy:
    mode:str='legacy'
    public_key:str=''
    issuer:str='inventario-u-security-lab'
    audience:str='inventario-u'
    subjects:tuple=()
    honeytoken_hash:str=''
    max_ttl_seconds:int=300

    @classmethod
    def from_environment(cls):
        mode=os.getenv('SECURITY_AUTH_MODE','legacy')
        if mode not in ('legacy','workload'):raise ValueError('Unsupported SECURITY_AUTH_MODE')
        if mode=='legacy':return cls()
        path=os.getenv('SECURITY_JWT_PUBLIC_KEY_FILE','')
        subjects=tuple(s.strip() for s in os.getenv('SECURITY_ALLOWED_SUBJECTS','').split(',') if s.strip())
        if not path or not subjects:raise ValueError('Workload identity requires a pinned public key and explicit subjects')
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',s) for s in subjects):raise ValueError('Invalid allowed subject')
        public=Path(path).read_text(encoding='ascii')
        # A verifier must never receive the issuer's private signing key.
        if 'PRIVATE KEY' in public:raise ValueError('Only a public verification key may be deployed')
        key=jwt.algorithms.get_default_algorithms()['EdDSA'].prepare_key(public)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not isinstance(key,Ed25519PublicKey):raise ValueError('Expected an Ed25519 public key')
        honey=os.getenv('SECURITY_HONEYTOKEN_SHA256','')
        if honey and not re.fullmatch('[a-f0-9]{64}',honey):raise ValueError('Expected honeytoken SHA256, never a plaintext credential')
        return cls(mode=mode,public_key=public,subjects=subjects,honeytoken_hash=honey)

    def announce(self):
        POLICY.labels(self.mode).set(1)

    def deny(self,request,reason,status=401,actor='unknown',token=''):
        current=round_identity()
        trace=correlation_id(getattr(request.state,'trace_id',None))
        DECISIONS.labels(current,'denied',reason).inc()
        DETECTIONS.labels(current,reason).inc()
        LAST_DETECTION.labels(current,reason).set(time.time())
        logger.warning('Machine identity rejected',extra={'event':'security_identity_detected',
            'trace_id':trace,'round':current,'control':'machine_identity','reason':reason,
            'decision':'denied','actor':actor,'credential_ref':hashlib.sha256(token.encode()).hexdigest()[:16] if token else 'absent',
            'path':request.url.path,'status':status})
        return JSONResponse(status_code=status,content={'detail':'Machine identity rejected','reason':reason,'trace_id':trace},
            headers={'X-Trace-Id':trace,'WWW-Authenticate':'Bearer'})

    def authorize(self,request:Request):
        if self.mode!='workload':raise RuntimeError('Legacy authorization belongs to the existing API-key middleware')
        header=request.headers.get('Authorization','')
        if not header.startswith('Bearer ') or len(header)>8192:return self.deny(request,'missing_or_malformed')
        token=header[7:]
        if self.honeytoken_hash and hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),self.honeytoken_hash):
            return self.deny(request,'honeytoken',token=token)
        try:
            claims=jwt.decode(token,self.public_key,algorithms=['EdDSA'],issuer=self.issuer,audience=self.audience,
                options={'require':['iss','aud','sub','exp','iat','nbf','jti','scope'],'strict_aud':True})
        except jwt.ExpiredSignatureError:return self.deny(request,'expired',token=token)
        except jwt.InvalidAudienceError:return self.deny(request,'wrong_audience',token=token)
        except jwt.InvalidIssuerError:return self.deny(request,'wrong_issuer',token=token)
        except jwt.InvalidTokenError:return self.deny(request,'invalid_token',token=token)
        if (any(type(claims[name]) is not int for name in ('iat','nbf','exp'))
            or not 0<claims['exp']-claims['iat']<=self.max_ttl_seconds
            or claims['nbf']!=claims['iat']
            or not re.fullmatch('[a-f0-9]{32}',claims.get('jti',''))):
            return self.deny(request,'invalid_lifetime_or_id',token=token)
        actor=claims['sub']
        if actor not in self.subjects:return self.deny(request,'unknown_subject',token=token)
        scope=claims.get('scope')
        if not isinstance(scope,str) or len(scope)>128:return self.deny(request,'invalid_scope',actor=actor,token=token)
        scopes=set(scope.split())
        required='inventory:read' if request.method in ('GET','HEAD','QUERY') else 'inventory:write'
        if not scopes or not scopes<={'inventory:read','inventory:write'} or required not in scopes:
            return self.deny(request,'scope_violation',403,actor=actor,token=token)
        request.state.machine_subject=actor
        DECISIONS.labels(round_identity(),'allowed','valid').inc()
        logger.info('Machine identity authorized',extra={'event':'security_identity_allowed',
            'trace_id':correlation_id(getattr(request.state,'trace_id',None)),'actor':actor,
            'decision':'allowed','reason':'valid','control':'machine_identity','path':request.url.path})
        return None
