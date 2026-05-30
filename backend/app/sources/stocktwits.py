import asyncio

from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker
from app.sources.anakin_client import AnakinWireClient


SYMBOL_STREAM_ACTION_ID = "st_symbol_stream"
TRENDING_ACTION_ID = "st_trending"


async def fetch_stocktwits(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    client = AnakinWireClient(settings)
    symbol_stream, trending = await asyncio.gather(
        client.run_action(SYMBOL_STREAM_ACTION_ID, {"symbol": ticker.nse_symbol, "limit": 30}),
        client.run_action(TRENDING_ACTION_ID, {"limit": 30}),
    )
    return SourceResult(
        status="ok",
        data={
            "symbol_stream": symbol_stream,
            "trending": trending,
        },
    )
