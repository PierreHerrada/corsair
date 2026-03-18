from __future__ import annotations

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class LogStreamer:
    def __init__(self, callback_url: str, run_id: str, secret: str) -> None:
        self._url = f"{callback_url}/api/v1/internal/runs/{run_id}/logs"
        self._headers = {
            "X-Internal-Secret": secret,
            "Content-Type": "application/json",
        }
        self._buffer: list[dict] = []
        self._max_batch = 10
        self._max_wait_ms = 500
        self._last_flush = time.monotonic()
        self._client = httpx.AsyncClient(timeout=10)

    async def add(self, line_type: str, content: str) -> None:
        self._buffer.append(
            {"type": line_type, "content": content, "timestamp": time.time()}
        )
        elapsed_ms = (time.monotonic() - self._last_flush) * 1000
        if len(self._buffer) >= self._max_batch or elapsed_ms >= self._max_wait_ms:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush = time.monotonic()

        for attempt in range(3):
            try:
                resp = await self._client.post(
                    self._url, json={"lines": batch}, headers=self._headers
                )
                resp.raise_for_status()
                return
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                # All retries exhausted — fall back to stdout
                for line in batch:
                    print(f"[{line['type']}] {line['content']}")

    async def close(self) -> None:
        await self.flush()
        await self._client.aclose()


async def post_status(
    callback_url: str,
    run_id: str,
    secret: str,
    status: str,
    exit_code: int | None = None,
    token_usage: dict | None = None,
    cost: dict | None = None,
    error_message: str | None = None,
) -> None:
    url = f"{callback_url}/api/v1/internal/runs/{run_id}/complete"
    headers = {"X-Internal-Secret": secret, "Content-Type": "application/json"}
    body: dict = {"status": status}
    if exit_code is not None:
        body["exit_code"] = exit_code
    if token_usage is not None:
        body["token_usage"] = token_usage
    if cost is not None:
        body["cost"] = cost
    if error_message is not None:
        body["error_message"] = error_message

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                return
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                logger.error("Failed to post status after 3 attempts")
                raise
