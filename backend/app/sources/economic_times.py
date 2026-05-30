from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker


async def fetch_economic_times(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    return SourceResult(
        status="missing_action",
        error="No Economic Times Wire action_id was discovered for stock news.",
    )
