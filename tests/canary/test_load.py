import io
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from deploy.canary import load


@pytest.mark.parametrize("rps,workers", [(0, 12), (201, 12), (80, 3), (80, 13), (80, 34)])
def test_load_limits(rps, workers):
    with pytest.raises(ValueError):
        load.Load("http://localhost", "key", rps, workers)


@pytest.mark.parametrize("percent,worker,expected", [(0, 0, "true"), (100, 0, "baseline"), (50, 0, "baseline"), (0, 6, None)])
def test_calibration_offsets_public_split(monkeypatch, percent, worker, expected):
    workload = load.Load("http://localhost", "key")
    workload.percent = percent
    workload.stop = Mock()
    workload.stop.is_set.side_effect = [False, True]
    workload.request = Mock(return_value=("stable", 200))
    monkeypatch.setattr(load.random, "random", lambda: .25)
    workload.worker(worker)
    workload.request.assert_called_once_with(expected)
    assert sum(workload.report()["public" if expected is None else "calibration"].values()) == 1


def test_http_failure_retains_track_and_network_failure_is_visible(monkeypatch):
    workload = load.Load("http://localhost", "key")
    error = HTTPError("http://localhost", 500, "injected", {"X-App-Track": "canary"}, io.BytesIO(b'{}'))
    monkeypatch.setattr(load, "urlopen", Mock(side_effect=error))
    assert workload.request() == ("canary", 500)
    monkeypatch.setattr(load, "urlopen", Mock(side_effect=URLError("unavailable")))
    assert workload.request() == ("unavailable", 0)
