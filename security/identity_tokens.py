"""Offline issuer; private keys and tokens never enter public artifacts."""
from pathlib import Path
import time
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import jwt


def create_keypair(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    private=folder/'issuer-private.pem';public=folder/'issuer-public.pem'
    if private.exists() or public.exists():raise ValueError('Refusing to overwrite an existing issuer keypair')
    key=Ed25519PrivateKey.generate()
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    private.chmod(0o600)
    public.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    return private,public


def issue(private_key,subject='coordinator-demo',scope='inventory:read',ttl=120,audience='inventario-u'):
    if not 1<=ttl<=300:raise ValueError('Machine tokens must expire within 300 seconds')
    now=int(time.time())
    claims={'iss':'inventario-u-security-lab','aud':audience,'sub':subject,'scope':scope,
        'iat':now,'nbf':now,'exp':now+ttl,'jti':uuid4().hex}
    return jwt.encode(claims,Path(private_key).read_bytes(),algorithm='EdDSA')
