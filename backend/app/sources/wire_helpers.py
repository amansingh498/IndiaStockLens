import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from app.models import SourceResult
from app.sources.anakin_client import AnakinWireClient


logger = logging.getLogger(__name__)


async def run_actions(
    client: AnakinWireClient,
    actions: Mapping[str, tuple[str, dict[str, Any]]],
) -> SourceResult:
    keys = list(actions)
    calls = [_run_action_with_logging(client, key, action_id, params) for key, (action_id, params) in actions.items()]
    results = await asyncio.gather(*calls, return_exceptions=True)

    data: dict[str, Any] = {}
    errors: list[str] = []
    for key, result in zip(keys, results, strict=True):
        if isinstance(result, Exception):
            errors.append(f"{key}: {result}")
        else:
            data[key] = result

    if not data and errors:
        return SourceResult(status="error", error="; ".join(errors))
    if errors:
        data["_errors"] = errors

    return SourceResult(status="ok", data=data)


async def _run_action_with_logging(
    client: AnakinWireClient,
    key: str,
    action_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    logger.info("wire action started", extra={"source_key": key, "action_id": action_id})
    try:
        result = await client.run_action(action_id, params)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.exception(
            "wire action failed",
            extra={"source_key": key, "action_id": action_id, "elapsed_ms": elapsed_ms},
        )
        raise

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info(
        "wire action completed",
        extra={"source_key": key, "action_id": action_id, "elapsed_ms": elapsed_ms},
    )
    return result
