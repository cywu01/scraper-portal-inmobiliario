"""Shared polite HTTP fetching: one client, a global concurrency cap, jitter, retries, block detection."""

import asyncio
import random
from typing import Callable, Literal

import httpx

import config

Outcome = Literal["ok", "gone", "failed"]


class BlockedError(RuntimeError):
    """Raised when too many requests in a row fail — the site is probably blocking us."""


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers=config.HEADERS, follow_redirects=True, timeout=config.TIMEOUT)


class Fetcher:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.sem = asyncio.Semaphore(config.CONCURRENCY)
        self.consecutive_failures = 0
        self.requests = 0

    async def get(self, url: str, classify: Callable[[httpx.Response], Outcome | None]) -> tuple[Outcome, httpx.Response | None]:
        """Fetch `url`. `classify` returns "ok", "gone" (valid page meaning no data), or None (retry).

        Returns ("failed", None) after MAX_RETRIES; raises BlockedError when failures pile up.
        """
        err = ""
        for attempt in range(1, config.MAX_RETRIES + 1):
            if self.consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                raise BlockedError(f"{self.consecutive_failures} consecutive failed requests; the site may be blocking. Stopping.")
            async with self.sem:
                await asyncio.sleep(random.uniform(*config.DELAY_RANGE))
                try:
                    r = await self.client.get(url)
                    self.requests += 1
                except httpx.HTTPError as e:
                    r, err = None, repr(e)

            if r is not None:
                outcome = classify(r)
                if outcome is not None:
                    self.consecutive_failures = 0
                    return outcome, r
                err = f"HTTP {r.status_code}, {len(r.content)} bytes"

            self.consecutive_failures += 1
            wait = 5 * 2 ** (attempt - 1) + random.uniform(0, 3)
            print(f"    [RETRY {attempt}/{config.MAX_RETRIES}] {err} → waiting {wait:.0f}s  ({url})")
            await asyncio.sleep(wait)

        print(f"    [FAIL] giving up on {url}")
        return "failed", None
