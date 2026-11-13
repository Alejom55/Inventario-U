"""Run separately from the experiment controller, on the dedicated proxy host."""

import json
import os
import time

from . import lease
from .providers import proxy_url, remove_latency, request_json


def configuration_from_environment():
    return {key: os.environ[name] for key, name in {
        "toxiproxy_url": "CHAOS_TOXIPROXY_URL", "proxy_name": "CHAOS_PROXY_NAME",
        "expected_upstream": "CHAOS_EXPECTED_UPSTREAM", "lease_db": "CHAOS_LEASE_DB",
    }.items()}


def tick(configuration):
    # An unavailable control plane must not advertise readiness for new faults.
    ready = False
    try:
        state = request_json(proxy_url(configuration))
        ready = state["upstream"] == configuration["expected_upstream"] and state["enabled"]
    finally:
        lease.heartbeat(configuration, ready)
    for run_id in lease.expired(configuration):
        remove_latency({**configuration, "run_id": run_id})
        print(json.dumps({"event": "lease_rollback_verified", "run_id": run_id}), flush=True)


def main():
    configuration = configuration_from_environment()
    while True:
        try:
            tick(configuration)
        except Exception as error:
            print(json.dumps({"event": "watchdog_control_error", "error_type": type(error).__name__}), flush=True)
        time.sleep(.5)


if __name__ == "__main__":
    main()
