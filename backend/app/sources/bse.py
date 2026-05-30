from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker


async def fetch_bse(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    return SourceResult(
        status="missing_action",
        error="No BSE Wire action_id was discovered for corporate filings.",
    )
