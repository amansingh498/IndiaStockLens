import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.anakin_api_key:
        raise RuntimeError("ANAKIN_API_KEY is not configured.")

    base = settings.anakin_base_url.rstrip("/")
    attempts = [
        (
            "search-current-key",
            "GET",
            f"{base}/wire/search",
            {"X-API-Key": settings.anakin_api_key},
            {"q": "Yahoo Finance stock quote"},
        ),
        (
            "search-fake-key",
            "GET",
            f"{base}/wire/search",
            {"X-API-Key": "ak-fake"},
            {"q": "Yahoo Finance stock quote"},
        ),
        (
            "search-no-key",
            "GET",
            f"{base}/wire/search",
            {},
            {"q": "Yahoo Finance stock quote"},
        ),
        (
            "wire-x-api-key-action_id",
            "POST",
            f"{base}/wire/task",
            {"X-API-Key": settings.anakin_api_key, "Content-Type": "application/json"},
            {"action_id": "st_trending", "params": {"limit": 1}},
        ),
        (
            "wire-x-api-key-actionId",
            "POST",
            f"{base}/wire/task",
            {"X-API-Key": settings.anakin_api_key, "Content-Type": "application/json"},
            {"actionId": "st_trending", "params": {"limit": 1}},
        ),
        (
            "wire-bearer-action_id",
            "POST",
            f"{base}/wire/task",
            {
                "Authorization": f"Bearer {settings.anakin_api_key}",
                "Content-Type": "application/json",
            },
            {"action_id": "st_trending", "params": {"limit": 1}},
        ),
        (
            "holocron-x-api-key-action_id",
            "POST",
            f"{base}/holocron/task",
            {"X-API-Key": settings.anakin_api_key, "Content-Type": "application/json"},
            {"action_id": "st_trending", "params": {"limit": 1}},
        ),
    ]

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        for name, method, url, headers, payload in attempts:
            if method == "GET":
                response = await client.get(url, headers=headers, params=payload)
            else:
                response = await client.post(url, headers=headers, json=payload)
            print(
                json.dumps(
                    {
                        "attempt": name,
                        "status_code": response.status_code,
                        "body": response.text[:800],
                    },
                    indent=2,
                )
            )
            if method != "GET" and 200 <= response.status_code < 300:
                break


if __name__ == "__main__":
    asyncio.run(main())
