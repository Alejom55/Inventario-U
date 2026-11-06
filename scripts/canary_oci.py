"""Execute bounded canary actions on an existing OCI instance, without Terraform apply."""

import argparse
import re

import oci
from oci.compute_instance_agent import models

from scripts.deploy_oci import wait_for_execution


def command_content(action, revision):
    if action not in {"install", "promote", "regression", "rollback"}:
        raise ValueError("Invalid canary action")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Full Git SHA required")
    preparation = [
        "#!/bin/bash", "set -euo pipefail", "sudo -n bash <<'CANARY_SCRIPT'", "set -euo pipefail",
        "cd /opt/inventario/source",
    ]
    if action == "install":
        preparation += [
            f"git fetch origin {revision} --depth=1",
            f"git checkout --detach {revision}",
            f"bash deploy/canary/install.sh {revision}",
        ]
    else:
        preparation += [
            f'test "$(cat /opt/inventario/deployed-revision)" = "{revision}"',
            f'test "$(git rev-parse HEAD)" = "{revision}"',
            f"/opt/inventario/sdk/bin/python -m deploy.canary.rollout {action}",
        ]
    return "\n".join([*preparation, "CANARY_SCRIPT"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "promote", "regression", "rollback"])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--compartment-id", required=True)
    args = parser.parse_args()
    client = oci.compute_instance_agent.ComputeInstanceAgentClient(oci.config.from_file())
    details = models.CreateInstanceAgentCommandDetails(
        compartment_id=args.compartment_id,
        display_name=f"canary-{args.action}-{args.revision[:12]}",
        execution_time_out_in_seconds=2400,
        target=models.InstanceAgentCommandTarget(instance_id=args.instance_id),
        content=models.InstanceAgentCommandContent(
            source=models.InstanceAgentCommandSourceViaTextDetails(text=command_content(args.action, args.revision)),
            output=models.InstanceAgentCommandOutputViaTextDetails(),
        ),
    )
    command_id = client.create_instance_agent_command(details).data.id
    print("Run Command:", command_id, flush=True)
    wait_for_execution(client, command_id, args.instance_id)
    print("Canary action completed:", args.action)


if __name__ == "__main__":
    main()
