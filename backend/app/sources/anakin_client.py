import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings


class AnakinClientError(RuntimeError):
    pass


_KEY_POOLS: dict[tuple[tuple[str, ...], int], "AnakinKeyPool"] = {}
_WIRE_SEMAPHORES: dict[tuple[int, int], asyncio.Semaphore] = {}


@dataclass
class _KeyState:
    key: str
    requests: deque[float] = field(default_factory=deque)


class AnakinKeyPool:
    def __init__(self, keys: list[str], requests_per_minute: int):
        self.states = [_KeyState(key) for key in keys]
        self.requests_per_minute = max(1, requests_per_minute)
        self.lock = asyncio.Lock()
        self.cursor = 0

    async def acquire(self) -> str:
        while True:
            wait_seconds = 0.0
            async with self.lock:
                now = asyncio.get_running_loop().time()
                for state in self.states:
                    while state.requests and now - state.requests[0] >= 60:
                        state.requests.popleft()

                for offset in range(len(self.states)):
                    index = (self.cursor + offset) % len(self.states)
                    state = self.states[index]
                    if len(state.requests) < self.requests_per_minute:
                        state.requests.append(now)
                        self.cursor = (index + 1) % len(self.states)
                        return state.key

                oldest = min(state.requests[0] for state in self.states if state.requests)
                wait_seconds = max(0.05, 60 - (now - oldest))

            await asyncio.sleep(wait_seconds)


def _get_key_pool(settings: Settings) -> AnakinKeyPool:
    keys = settings.get_anakin_api_keys()
    if not keys:
        raise AnakinClientError("ANAKIN_API_KEY or ANAKIN_API_KEYS is not configured.")

    pool_key = (tuple(keys), settings.anakin_requests_per_minute)
    pool = _KEY_POOLS.get(pool_key)
    if pool is None:
        pool = AnakinKeyPool(keys, settings.anakin_requests_per_minute)
        _KEY_POOLS[pool_key] = pool
    return pool


def _get_wire_semaphore(settings: Settings) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    limit = max(1, settings.anakin_wire_concurrency)
    semaphore_key = (id(loop), limit)
    semaphore = _WIRE_SEMAPHORES.get(semaphore_key)
    if semaphore is None:
        semaphore = asyncio.Semaphore(limit)
        _WIRE_SEMAPHORES[semaphore_key] = semaphore
    return semaphore


class AnakinWireClient:
    def __init__(self, settings: Settings):
        self.key_pool = _get_key_pool(settings)

        self.settings = settings
        self.base_headers = {
            "Content-Type": "application/json",
        }

    async def search_actions(self, query: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            return await self._request_json(
                client,
                "GET",
                f"{self.settings.anakin_base_url}/wire/search",
                params={"q": query},
            )

    async def run_action(
        self,
        action_id: str,
        params: dict[str, Any],
        credential_id: str | None = None,
    ) -> dict[str, Any]:
        async with _get_wire_semaphore(self.settings):
            return await self._run_action(action_id, params, credential_id)

    async def _run_action(
        self,
        action_id: str,
        params: dict[str, Any],
        credential_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action_id": action_id, "params": params}
        if credential_id:
            payload["credential_id"] = credential_id

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            job = await self._request_json(
                client,
                "POST",
                f"{self.settings.anakin_base_url}/wire/task",
                json=payload,
            )
            job_id = job.get("job_id") or job.get("jobId") or job.get("id")
            if not job_id:
                data = job.get("data")
                if data is not None:
                    return data
                raise AnakinClientError(f"Wire task response did not include job_id: {job}")

            return await self._poll_job(client, job_id)

    async def _poll_job(self, client: httpx.AsyncClient, job_id: str) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + self.settings.wire_max_poll_seconds

        while asyncio.get_running_loop().time() < deadline:
            job = await self._request_json(
                client,
                "GET",
                f"{self.settings.anakin_base_url}/wire/jobs/{job_id}",
            )
            status = str(job.get("status", "")).lower()

            if status in {"completed", "complete", "success", "succeeded"}:
                return job.get("data") or job.get("result") or job
            if status in {"failed", "error", "cancelled"}:
                raise AnakinClientError(f"Wire job {job_id} failed: {job}")

            await asyncio.sleep(self.settings.wire_poll_interval_seconds)

        raise TimeoutError(f"Wire job {job_id} exceeded poll timeout.")

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        for attempt in range(4):
            headers = await self._headers()
            response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code != 429:
                self._raise_for_status(response)
                return response.json()

            if attempt == 3:
                self._raise_for_status(response)

            await asyncio.sleep(self._retry_delay(response, attempt))

        raise AnakinClientError("Unexpected Anakin request retry exhaustion.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass

        try:
            payload = response.json()
            message = json.dumps(payload)
        except ValueError:
            message = response.text

        if "RATE_LIMIT_EXCEEDED" in message:
            return float(15 * (attempt + 1))
        return float(2**attempt)

    async def _headers(self) -> dict[str, str]:
        api_key = await self.key_pool.acquire()
        return {**self.base_headers, "X-API-Key": api_key}

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnakinClientError(
                f"{exc.response.status_code} from {exc.response.url}: {exc.response.text}"
            ) from exc
