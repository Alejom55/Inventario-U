"""Deploy a pushed commit with OCI Run Command, without opening SSH."""

import argparse
import re
import time

import oci
from oci.compute_instance_agent import models


def command_content(revision):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Use a full, lowercase Git commit SHA")
    return "\n".join([
        "#!/bin/bash", "set -euo pipefail",
        "for attempt in {1..120}; do",
        "  if test -f /opt/inventario/bootstrap.ready; then break; fi",
        "  sleep 10", "done",
        "test -f /opt/inventario/bootstrap.ready",
        "sudo -n /opt/inventario/deploy.sh " + revision,
    ])


def wait_for_execution(client, command_id, instance_id, timeout=2400):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            execution = client.get_instance_agent_command_execution(command_id, instance_id).data
        except oci.exceptions.ServiceError as error:
            if error.status != 404:
                raise
        else:
            if execution.lifecycle_state == "SUCCEEDED":
                if execution.content.exit_code != 0:
                    raise RuntimeError("Run Command returned a nonzero exit code")
                return
            if execution.lifecycle_state in {"FAILED", "TIMED_OUT", "CANCELED"}:
                raise RuntimeError("Deployment failed: " + execution.lifecycle_state)
        time.sleep(15)
    client.cancel_instance_agent_command(command_id)
    raise TimeoutError("Deployment timed out; cancellation requested")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    script = command_content(args.revision)
    client = oci.compute_instance_agent.ComputeInstanceAgentClient(oci.config.from_file())
    details = models.CreateInstanceAgentCommandDetails(
        compartment_id=args.compartment_id,
        display_name="inventario-" + args.revision[:12],
        execution_time_out_in_seconds=2400,
        target=models.InstanceAgentCommandTarget(instance_id=args.instance_id),
        content=models.InstanceAgentCommandContent(
            source=models.InstanceAgentCommandSourceViaTextDetails(text=script),
            output=models.InstanceAgentCommandOutputViaTextDetails(),
        ),
    )
    command_id = client.create_instance_agent_command(details).data.id
    print("Run Command:", command_id, flush=True)
    wait_for_execution(client, command_id, args.instance_id)
    print("Deployment and smoke checks succeeded:", args.revision)


if __name__ == "__main__":
    main()
