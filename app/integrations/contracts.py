"""One definition of the two entity routes shared by clients and preflight."""

import hashlib
import json
import os
from urllib.parse import quote


DEPENDENCIES = {
    "deportBack": ("DEPORTBACK_API_URL", "DEPORTBACK_ENTITY_PATH", "/deportistas/{id}"),
    "api-fastify": ("FASTIFY_API_URL", "FASTIFY_ENTITY_PATH", "/articulos/{id}"),
}


def path_template(service, environment=None):
    environment = os.environ if environment is None else environment
    variable, template_variable, default = DEPENDENCIES[service]
    template = environment.get(template_variable) or default
    if not template.startswith("/") or template.startswith("//") or template.count("{id}") != 1 or any(x in template for x in ("..", "?", "#", "\\", "\r", "\n")):
        raise ValueError("Entity path must be an absolute route with one {id} placeholder")
    return template


def entity_path(service, identity):
    return path_template(service).replace("{id}", quote(str(identity), safe=""))


def configuration_fingerprint(environment=None):
    environment = os.environ if environment is None else environment
    contracts = {
        service: {"url": environment.get(settings[0], "").rstrip("/"), "path": path_template(service, environment)}
        for service, settings in DEPENDENCIES.items()
    }
    return hashlib.sha256(json.dumps(contracts, sort_keys=True).encode()).hexdigest()
