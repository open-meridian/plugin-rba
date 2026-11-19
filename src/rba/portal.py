"""The Reserve Bank of Australia's website, where its statistical tables are
served, and its stand-in.

Four requests are made, and nothing else, each a whole table's CSV
(https://www.rba.gov.au/statistics/tables/):

- F1, money market rates, `/statistics/tables/csv/f1-data.csv` (from 2011);
- F2, government bond yields, `/statistics/tables/csv/f2-data.csv` (2013);
- F17, zero-coupon yields, `/statistics/tables/csv/f17-yields.csv` (2017);
- F11.1, exchange rates, `/statistics/tables/csv/f11.1-data.csv` (2023).

Read from the RBA itself: no key, no account. Its site states no rate
limit; the plugin asks one request at a time, at most one every two seconds,
says who it is in its User-Agent, and checks each table every hour with the
table's `Last-Modified` as `If-Modified-Since`, so a table not changed is
answered 304 and not sent again.

`SyntheticPortal` answers from the real responses committed under
responses/ (responses/index.json), recorded on 2026-11-19, each table
whole, and 304 to a request naming its recording's Last-Modified, so the
plugin's tests and its e2e run on them, offline, the same on any day.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import resources
from typing import Protocol

from .series import F1, F2, F11, F17, TABLES

BASE = "https://www.rba.gov.au"
_TABLES = "/statistics/tables/csv/"
#: Each table's address.
PATHS = {
    F1: _TABLES + "f1-data.csv",
    F2: _TABLES + "f2-data.csv",
    F17: _TABLES + "f17-yields.csv",
    F11: _TABLES + "f11.1-data.csv",
}
USER_AGENT = "meridian-rba (+https://github.com/open-meridian/plugin-rba)"
SPACING = 2.0
TIMEOUT = 120.0
#: The most an answer may be: F17 is some 0.6 MB.
MOST_BYTES = 16 * 1024 * 1024


def table_of(path: str) -> str:
    """Which table an address asks, or none."""
    return next((t for t, at in PATHS.items() if path == at), "")


class PortalUnreachable(Exception):  # noqa: N818 - what the RBA's website was
    """The website could not be asked: no answer, or not in time."""


@dataclass(frozen=True)
class Fetched:
    """One answer, as received: 304 where the table had not changed."""

    path: str
    status: int
    body: bytes
    fetched_at: datetime
    date: str = ""
    last_modified: str = ""

    @property
    def url(self) -> str:
        return BASE + self.path

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class Portal(Protocol):
    mode: str

    async def get(self, path: str, since: str = "") -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class LivePortal:
    """The RBA's website itself."""

    mode = "live"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def get(self, path: str, since: str = "") -> Fetched:
        async with self._lock:
            wait = self._last + SPACING - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await asyncio.to_thread(self._get, path, since)
            finally:
                self._last = time.monotonic()

    def _get(self, path: str, since: str) -> Fetched:
        headers = {"User-Agent": USER_AGENT}
        if since:
            headers["If-Modified-Since"] = since
        request = urllib.request.Request(BASE + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - the RBA's https address
                body = answer.read(MOST_BYTES + 1)
                status = answer.status
                said = answer.headers
        except urllib.error.HTTPError as refused:
            body = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status, said = refused.code, refused.headers
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise PortalUnreachable(f"{BASE}{path[:80]}: {type(reason).__name__}") from failed
        if len(body) > MOST_BYTES:
            raise PortalUnreachable(f"{BASE}{path[:80]}: answered more than {MOST_BYTES} bytes")
        return Fetched(
            path,
            status,
            body,
            self._now(),
            date=said.get("Date", "") if said else "",
            last_modified=said.get("Last-Modified", "") if said else "",
        )


@dataclass(frozen=True)
class Recording:
    """One recorded answer: its body, Date, Last-Modified and last day."""

    body: bytes
    said: str
    last_modified: str
    last_day: date


class SyntheticPortal:
    """The responses committed under responses/: each table answered whole
    under its recording's Date, or 304 where asked since its Last-Modified."""

    mode = "synthetic"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("responses")
        index = json.loads(held.joinpath("index.json").read_text(encoding="utf-8"))
        self.recordings = {}
        for table in TABLES:
            entry = index[table]
            body = held.joinpath(entry["file"]).read_bytes()
            self.recordings[table] = Recording(
                gzip.decompress(body) if entry["file"].endswith(".gz") else body,
                str(entry["date"]),
                str(entry["last_modified"]),
                date.fromisoformat(entry["last_day"]),
            )
        self.asked: list[str] = []

    async def get(self, path: str, since: str = "") -> Fetched:
        self.asked.append(path)
        recording = self.recordings.get(table_of(path))
        if recording is None:
            return Fetched(path, 404, b"Not found", self._now())
        if since and since == recording.last_modified:
            return Fetched(path, 304, b"", self._now(), recording.said, recording.last_modified)
        return Fetched(
            path, 200, recording.body, self._now(), recording.said, recording.last_modified
        )


def portal(synthetic: bool, now: Callable[[], datetime] = utc_now) -> Portal:
    return SyntheticPortal(now) if synthetic else LivePortal(now)
