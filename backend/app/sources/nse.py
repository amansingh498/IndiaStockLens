from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker
from app.sources.anakin_client import AnakinWireClient
from app.sources.wire_helpers import run_actions


async def fetch_nse(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    client = AnakinWireClient(settings)
    return await run_actions(
        client,
        {
            "corporate_actions": ("nse_corporate_actions", {"symbol": ticker.nse_symbol}),
            "insider_trading": ("nse_insider_trading", {"symbol": ticker.nse_symbol}),
            "board_meetings": ("nse_board_meetings", {"symbol": ticker.nse_symbol}),
        },
    )
