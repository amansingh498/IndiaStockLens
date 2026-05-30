from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker


async def fetch_sebi(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    return SourceResult(
        status="missing_action",
        error="No SEBI Wire action_id was discovered for company orders or notices.",
    )
