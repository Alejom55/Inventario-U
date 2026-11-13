"""SQLite leases shared with a watchdog process on the Toxiproxy host."""

import hashlib
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time


def signature(configuration):
    return hashlib.sha256(json.dumps({key: configuration[key] for key in ("toxiproxy_url", "proxy_name", "expected_upstream")}, sort_keys=True).encode()).hexdigest()


@contextmanager
def connect(configuration, create=False):
    path = Path(configuration["lease_db"])
    if not path.is_absolute():
        raise ValueError("The server-side lease database requires an absolute path")
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        raise ValueError("Independent watchdog is not initialized")
    connection = sqlite3.connect(path, timeout=3)
    try:
        if create:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS heartbeat (scope TEXT PRIMARY KEY, checked REAL, ready INTEGER);
            CREATE TABLE IF NOT EXISTS lease (scope TEXT PRIMARY KEY, run_id TEXT, expires REAL);
            """)
        with connection:
            yield connection
    finally:
        connection.close()


def heartbeat(configuration, ready=True, now=None):
    now = time.time() if now is None else now
    with connect(configuration, create=True) as database:
        database.execute("INSERT OR REPLACE INTO heartbeat VALUES (?,?,?)", (signature(configuration), now, int(ready)))


def ready(configuration, now=None):
    now = time.time() if now is None else now
    try:
        with connect(configuration) as database:
            row = database.execute("SELECT checked,ready FROM heartbeat WHERE scope=?", (signature(configuration),)).fetchone()
        return bool(row and row[1] and 0 <= now-row[0] <= 10)
    except (ValueError, OSError, sqlite3.Error):
        return False


def arm(configuration, ttl=75, now=None):
    now = time.time() if now is None else now
    if not 1 <= ttl <= 90:
        raise ValueError("Lease lifetime must be 1..90 seconds")
    with connect(configuration) as database:
        database.execute("BEGIN IMMEDIATE")
        scope = signature(configuration)
        state = database.execute("SELECT checked,ready FROM heartbeat WHERE scope=?", (scope,)).fetchone()
        if not state or not state[1] or not 0 <= now-state[0] <= 10:
            raise ValueError("Independent watchdog heartbeat is missing, stale or unhealthy")
        try:
            database.execute("INSERT INTO lease VALUES (?,?,?)", (scope, configuration["run_id"], now+ttl))
        except sqlite3.IntegrityError:
            raise ValueError("Another experiment lease is active; verified cleanup is required") from None


def release(configuration):
    with connect(configuration) as database:
        database.execute("DELETE FROM lease WHERE scope=? AND run_id=?", (signature(configuration), configuration["run_id"]))


def expired(configuration, now=None):
    now = time.time() if now is None else now
    with connect(configuration, create=True) as database:
        return [row[0] for row in database.execute("SELECT run_id FROM lease WHERE scope=? AND expires<=?", (signature(configuration), now))]
