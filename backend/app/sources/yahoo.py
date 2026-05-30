from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker
from app.sources.anakin_client import AnakinWireClient


async def fetch_yahoo_finance(
    ticker: ResolvedTicker,
    settings: Settings,
) -> SourceResult:
    client = AnakinWireClient(settings)
    data = await client.run_action("yf_quote", {"ticker": ticker.yahoo_symbol})
    return SourceResult(status="ok", data={"quote": data})
