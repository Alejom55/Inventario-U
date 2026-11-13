"""Reuse an installed image only when every application build input is unchanged."""

import re
import subprocess
import sys

from deploy.canary.rollout import load_env


def reusable_image(revision, env_path="/opt/inventario/canary.env"):
    values = load_env(env_path)
    previous = values.get("APP_REVISION", "")
    image = values.get("CANARY_IMAGE", "")
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (previous, revision)):
        raise ValueError("Invalid revision")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("Invalid image")
    subprocess.run([
        "git", "diff", "--quiet", previous, revision, "--",
        "app", "Dockerfile", "pyproject.toml", "uv.lock", ".dockerignore",
    ], check=True)
    actual = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True,
    ).strip()
    if actual != image:
        raise ValueError("Image identity mismatch")
    return image


if __name__ == "__main__":
    try:
        print(reusable_image(sys.argv[1]))
    except (OSError, ValueError, subprocess.SubprocessError):
        sys.exit(1)
