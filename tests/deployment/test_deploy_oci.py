from unittest.mock import Mock

import oci
import pytest

from scripts import deploy_oci


@pytest.mark.parametrize("revision", ["main", "a" * 39, "a" * 41, "A" * 40, "a; echo secret"])
def test_command_rejects_shell_injection(revision):
    with pytest.raises(ValueError):
        deploy_oci.command_content(revision)


def test_command_is_small_and_contains_only_validated_revision():
    script = deploy_oci.command_content("a" * 40)
    assert len(script.encode()) < 4096
    assert script.endswith("sudo -n /opt/inventario/deploy.sh " + "a" * 40)
    assert "bootstrap.ready" in script


def test_waits_for_success_and_retries_not_yet_visible(monkeypatch):
    monkeypatch.setattr(deploy_oci.time, "sleep", Mock())
    client = Mock()
    client.get_instance_agent_command_execution.side_effect = [
        oci.exceptions.ServiceError(404, "NotFound", {}, "not ready"),
        Mock(data=Mock(lifecycle_state="IN_PROGRESS")),
        Mock(data=Mock(lifecycle_state="SUCCEEDED", content=Mock(exit_code=0))),
    ]
    deploy_oci.wait_for_execution(client, "command", "instance")
    assert client.get_instance_agent_command_execution.call_count == 3


@pytest.mark.parametrize("state", ["FAILED", "TIMED_OUT", "CANCELED"])
def test_failed_remote_commands_fail_the_pipeline(state):
    client = Mock()
    client.get_instance_agent_command_execution.return_value.data.lifecycle_state = state
    with pytest.raises(RuntimeError, match=state):
        deploy_oci.wait_for_execution(client, "command", "instance")


def test_nonzero_exit_is_not_success():
    client = Mock()
    client.get_instance_agent_command_execution.return_value.data = Mock(lifecycle_state="SUCCEEDED", content=Mock(exit_code=1))
    with pytest.raises(RuntimeError, match="nonzero"):
        deploy_oci.wait_for_execution(client, "command", "instance")


def test_unauthorized_is_not_retried():
    client = Mock()
    client.get_instance_agent_command_execution.side_effect = oci.exceptions.ServiceError(401, "Unauthorized", {}, "no access")
    with pytest.raises(oci.exceptions.ServiceError):
        deploy_oci.wait_for_execution(client, "command", "instance")


def test_timeout_requests_cancellation():
    client = Mock()
    with pytest.raises(TimeoutError):
        deploy_oci.wait_for_execution(client, "command", "instance", timeout=0)
    client.cancel_instance_agent_command.assert_called_once_with("command")
