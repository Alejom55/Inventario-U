"""Read instance metadata and Vault; keep secrets in a root-only local file."""

import base64
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import oci


def render(config, password, api_key, revision):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Invalid Git revision")
    if not re.fullmatch(r"[A-Za-z0-9]{32}", password):
        raise ValueError("Invalid database password format")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", api_key):
        raise ValueError("Invalid API key format")
    values = {
        "APP_REVISION": revision,
        "POSTGRES_PASSWORD": password,
        "TEAM_API_KEY": api_key,
        "OCI_REGION": config["OCI_REGION"],
        "OCI_NAMESPACE": config["OCI_NAMESPACE"],
        "OCI_BUCKET_NAME": config["OCI_BUCKET_NAME"],
        "DEPORTBACK_API_URL": config.get("DEPORTBACK_API_URL", ""),
        "FASTIFY_API_URL": config.get("FASTIFY_API_URL", ""),
    }
    for name, value in values.items():
        if not isinstance(value, str) or any(ord(char) < 32 for char in value):
            raise ValueError("Invalid environment value: " + name)
        if name.endswith("_API_URL") and value:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("External API URL must use HTTPS without credentials")
    return "".join(name + "=" + json.dumps(value.replace("$", "$$")) + "\n" for name, value in values.items())


def main(revision, destination):
    request = Request(
        "http://169.254.169.254/opc/v2/instance/metadata/",
        headers={"Authorization": "Bearer Oracle"},
    )
    with urlopen(request, timeout=10) as response:
        config = json.loads(json.load(response)["inventory_config"])
    client = oci.secrets.SecretsClient(
        {"region": config["OCI_REGION"]},
        signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner(),
        retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY,
    )

    def secret(identifier):
        bundle = client.get_secret_bundle(identifier).data.secret_bundle_content
        return base64.b64decode(bundle.content, validate=True).decode("utf-8")

    content = render(config, secret(config["DATABASE_SECRET_ID"]), secret(config["TEAM_SECRET_ID"]), revision)
    target = Path(destination)
    temporary = target.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    os.chmod(temporary, 0o600)
    temporary.replace(target)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
