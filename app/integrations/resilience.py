"""Process-local circuit breakers; baseline preserves the previous client behavior."""

import math
import os
import threading
import time

from prometheus_client import Gauge


CIRCUIT_STATE = Gauge(
    "inventory_dependency_circuit_state", "Closed=0, half-open=0.5, open=1",
    ["service"],
)


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failures=3, cooldown=10, clock=time.monotonic):
        self.threshold, self.cooldown, self.clock = failures, cooldown, clock
        self.lock = threading.Lock()
        self.failures = 0
        self.opened_at = None
        self.probing = False
        self.generation = 0

    @property
    def state(self):
        with self.lock:
            return 0.5 if self.probing else (1 if self.opened_at is not None else 0)

    def acquire(self):
        with self.lock:
            if self.opened_at is not None:
                if self.probing or self.clock() - self.opened_at < self.cooldown:
                    raise CircuitOpen()
                self.probing = True
            return self.generation

    def success(self, generation):
        with self.lock:
            # An old in-flight response cannot close a circuit opened by newer failures.
            if generation == self.generation:
                self.failures, self.opened_at, self.probing = 0, None, False

    def failure(self, generation):
        with self.lock:
            if generation != self.generation:
                return
            self.failures += 1
            if self.probing or self.failures >= self.threshold:
                self.opened_at, self.probing = self.clock(), False
                self.generation += 1


_breakers = {}
_lock = threading.Lock()


def protection(service, base_url):
    mode = os.getenv("RESILIENCE_MODE", "baseline")
    if mode not in {"baseline", "protected"}:
        raise ValueError("RESILIENCE_MODE must be baseline or protected")
    if mode == "baseline":
        return 5.0, None
    variable = {"deportBack": "DEPORTBACK_TIMEOUT_SECONDS", "api-fastify": "FASTIFY_TIMEOUT_SECONDS"}.get(service)
    timeout = float(os.getenv(variable, "0.5")) if variable else 0.5
    if not math.isfinite(timeout) or not 0.05 <= timeout <= 5:
        raise ValueError("Dependency timeout must be between 0.05 and 5 seconds")
    with _lock:
        breaker = _breakers.setdefault((service, base_url), CircuitBreaker())
    return timeout, breaker


def observe(service, breaker):
    # Keep metric cardinality bounded even if this helper gains additional callers.
    if service in {"deportBack", "api-fastify"}:
        CIRCUIT_STATE.labels(service).set(breaker.state if breaker else 0)
