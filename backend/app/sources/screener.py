from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker
from app.sources.anakin_client import AnakinWireClient
from app.sources.wire_helpers import run_actions


async def fetch_screener(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    client = AnakinWireClient(settings)
    return await run_actions(
        client,
        {
            "overview": ("scr_company_overview", {"company": ticker.nse_symbol}),
            "quarterly": ("scr_company_quarterly", {"company": ticker.nse_symbol}),
        },
    )
