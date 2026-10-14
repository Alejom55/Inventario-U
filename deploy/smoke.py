"""Run inside the API container after deployment; never print the API key."""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid


def request(path, body=None, authenticated=True):
    headers = {"Content-Type": "application/json"}
    if authenticated:
        headers["X-Api-Key"] = os.environ["TEAM_API_KEY"]
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request("http://127.0.0.1:8000/api/v2" + path, data=data, headers=headers), timeout=45) as response:
        return json.load(response)


def main():
    assert request("/health", authenticated=False)["status"] == "ok"
    try:
        request("/skus", authenticated=False)
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError("API must require authentication")
    assert isinstance(request("/skus"), list)
    trace = "deploy-" + uuid.uuid4().hex
    payload = {"source": "deployment-smoke", "trace": trace}
    assert request("/storage", {"trace_id": trace, "data": payload})["status"] == "stored"
    recovered = request("/storage/" + trace)
    assert recovered == payload
    assert request("/storage?prefix=flujos%2F" + trace)["objects"]
    print("OK: health, authentication, PostgreSQL, Object Storage write/read/list")


if __name__ == "__main__":
    main()
