import io
import json
from unittest.mock import Mock

import pytest

from deploy.canary import load, rollout
from scripts.canary_oci import command_content


@pytest.mark.parametrize("action", ["install", "promote", "regression", "rollback"])
def test_oci_action_keeps_existing_sudo_boundary(action):
    script = command_content(action, "a" * 40)
    assert "sudo -n /opt/inventario/deploy.sh " + "a" * 40 in script
    assert "sudo -n bash" not in script
    assert len(script) < 4096


@pytest.mark.parametrize("action,sha", [("destroy", "a" * 40), ("install", "main; echo secret")])
def test_oci_rejects_unknown_actions_and_shell_injection(action, sha):
    with pytest.raises(ValueError):
        command_content(action, sha)


@pytest.mark.parametrize("percent,counts,passed", [
    (0, {"stable:200": 1000}, True), (100, {"canary:200": 1000}, True),
    (10, {"stable:200": 900, "canary:200": 100}, True),
    (50, {"stable:200": 500, "canary:200": 500}, True),
    (10, {"stable:200": 1000}, False), (0, {"stable:200": 499}, False),
    (0, {"unavailable:0": 1000}, False),
])
def test_real_traffic_distribution(percent, counts, passed):
    workload = load.Load("http://localhost", "secret")
    workload.public.update(counts)
    assert rollout.distribution(workload.report(), percent) is passed


def test_stage_restores_disk_config_when_validation_fails(tmp_path, monkeypatch):
    folder = tmp_path / "runtime"
    folder.mkdir()
    config = folder / "proxy.conf"
    config.write_text("previous")
    monkeypatch.setattr(rollout, "FOLDER", tmp_path)
    controller = object.__new__(rollout.Rollout)
    controller.key = "k" * 32
    controller.compose = Mock(side_effect=RuntimeError("invalid nginx config"))
    with pytest.raises(RuntimeError):
        controller.stage(10)
    assert config.read_text() == "previous"


def test_exception_during_analysis_rolls_back_and_clears_fault(monkeypatch):
    controller = object.__new__(rollout.Rollout)
    controller.values = {"CANARY_IMAGE": "sha256:" + "a" * 64, "APP_REVISION": "b" * 40}
    controller.key, controller.base_url = "secret", "http://localhost"
    controller.event, controller.stage, controller.fault, controller.rollback = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(rollout, "Load", Mock(side_effect=RuntimeError("load failed")))
    with pytest.raises(RuntimeError, match="load failed"):
        controller.run("promote")
    controller.rollback.assert_called_once()
    assert controller.fault.call_count == 2


def test_immutable_image_and_secret_env_loading(tmp_path):
    env = tmp_path / "runtime.env"
    env.write_text('CANARY_IMAGE="mutable:latest"\n')
    with pytest.raises(ValueError, match="immutable"):
        rollout.Rollout(env, tmp_path / "evidence.jsonl")
    env.write_text('KEY="https://example.com/$$route"\n')
    assert rollout.load_env(env)["KEY"] == "https://example.com/$route"
