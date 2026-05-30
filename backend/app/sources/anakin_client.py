import asyncio
from typing import Any

import httpx

from app.config import Settings


class AnakinClientError(RuntimeError):
    pass


class AnakinWireClient:
    def __init__(self, settings: Settings):
        if not settings.anakin_api_key:
            raise AnakinClientError("ANAKIN_API_KEY is not configured.")

        self.settings = settings
        self.headers = {
            "X-API-Key": settings.anakin_api_key,
            "Content-Type": "application/json",
        }

    async def search_actions(self, query: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(
                f"{self.settings.anakin_base_url}/wire/search",
                headers=self.headers,
                params={"q": query},
            )
            self._raise_for_status(response)
            return response.json()

    async def run_action(
        self,
        action_id: str,
        params: dict[str, Any],
        credential_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action_id": action_id, "params": params}
        if credential_id:
            payload["credential_id"] = credential_id

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            submitted = await client.post(
                f"{self.settings.anakin_base_url}/wire/task",
                headers=self.headers,
                json=payload,
            )
            self._raise_for_status(submitted)
            job = submitted.json()
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
            response = await client.get(
                f"{self.settings.anakin_base_url}/wire/jobs/{job_id}",
                headers=self.headers,
            )
            self._raise_for_status(response)
            job = response.json()
            status = str(job.get("status", "")).lower()

            if status in {"completed", "complete", "success", "succeeded"}:
                return job.get("data") or job.get("result") or job
            if status in {"failed", "error", "cancelled"}:
                raise AnakinClientError(f"Wire job {job_id} failed: {job}")

            await asyncio.sleep(self.settings.wire_poll_interval_seconds)

        raise TimeoutError(f"Wire job {job_id} exceeded poll timeout.")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnakinClientError(
                f"{exc.response.status_code} from {exc.response.url}: {exc.response.text}"
            ) from exc
