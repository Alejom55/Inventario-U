"""Bounded concurrent read-only workload with a separate public split sample."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Load:
    def __init__(self, base_url, key, rps=80, workers=12):
        if not 1 <= rps <= 200 or not 3 <= workers <= 32:
            raise ValueError("Load must use 1..200 RPS and 3..32 workers")
        self.base_url, self.key = base_url.rstrip("/"), key
        self.rps, self.workers = rps, workers
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.public = Counter()
        self.calibration = Counter()

    def request(self, selection=None):
        headers = {"X-Api-Key": self.key, "Content-Type": "application/json"}
        if selection:
            headers["X-Canary"] = selection
        request = Request(self.base_url + "/api/live/inventario/query", data=b"{}", headers=headers, method="QUERY")
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError):
            return "unavailable", 0
        with response:
            response.read()
            return response.headers.get("X-App-Track", "unavailable"), response.status

    def worker(self, index):
        # Half the workers send balanced baseline/canary probes, even at 0/100%.
        mode = ("baseline" if index % 2 == 0 else "true") if index < self.workers // 2 else None
        interval = self.workers / self.rps
        while not self.stop.is_set():
            start = time.monotonic()
            track, status = self.request(mode)
            with self.lock:
                (self.calibration if mode else self.public)[f"{track}:{status}"] += 1
            self.stop.wait(max(0, interval - (time.monotonic() - start)))

    def __enter__(self):
        self.pool = ThreadPoolExecutor(max_workers=self.workers)
        self.futures = [self.pool.submit(self.worker, i) for i in range(self.workers)]
        return self

    def reset(self):
        with self.lock:
            self.public.clear()
            self.calibration.clear()

    def report(self):
        with self.lock:
            public, calibration = dict(self.public), dict(self.calibration)
        n = sum(public.values())
        canary = sum(value for label, value in public.items() if label.startswith("canary:"))
        return {"public": public, "calibration": calibration, "public_requests": n,
                "public_canary_ratio": canary / n if n else None}

    def __exit__(self, *args):
        self.stop.set()
        self.pool.shutdown(wait=True)
        for future in self.futures:
            future.result()
