import subprocess
from unittest.mock import patch

import pytest

from deploy.canary.reuse_image import reusable_image


def test_reuses_only_verified_image():
    image = "sha256:" + "a" * 64
    with patch("deploy.canary.reuse_image.load_env", return_value={"APP_REVISION": "b" * 40, "CANARY_IMAGE": image}), patch("subprocess.run") as diff, patch("subprocess.check_output", return_value=image + "\n"):
        assert reusable_image("c" * 40) == image
        assert diff.call_args.args[0][-5:] == ["app", "Dockerfile", "pyproject.toml", "uv.lock", ".dockerignore"]


def test_changed_build_inputs_require_rebuild():
    with patch("deploy.canary.reuse_image.load_env", return_value={"APP_REVISION": "b" * 40, "CANARY_IMAGE": "sha256:" + "a" * 64}), patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")), patch("subprocess.check_output") as inspect:
        with pytest.raises(subprocess.CalledProcessError):
            reusable_image("c" * 40)
        inspect.assert_not_called()


def test_image_identity_mismatch_fails_closed():
    with patch("deploy.canary.reuse_image.load_env", return_value={"APP_REVISION": "b" * 40, "CANARY_IMAGE": "sha256:" + "a" * 64}), patch("subprocess.run"), patch("subprocess.check_output", return_value="sha256:" + "d" * 64):
        with pytest.raises(ValueError, match="identity"):
            reusable_image("c" * 40)
