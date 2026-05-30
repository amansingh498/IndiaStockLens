from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker


async def fetch_moneycontrol(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    return SourceResult(
        status="missing_action",
        error="No Moneycontrol Wire action_id was discovered for analyst recommendations.",
    )
