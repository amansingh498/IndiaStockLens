import asyncio
from app.config import Settings
from app.models import SourceResult
from app.pipeline.normalization import ResolvedTicker
from app.sources.anakin_client import AnakinWireClient


async def fetch_nse(ticker: ResolvedTicker, settings: Settings) -> SourceResult:
    client = AnakinWireClient(settings)
    
    # Run multiple NSE actions in parallel
    actions = {
        "quote": client.run_action("nse_quote", {"symbol": ticker.nse_symbol}),
        "corporate_actions": client.run_action("nse_corporate_actions", {"symbol": ticker.nse_symbol}),
        "insider_trading": client.run_action("nse_insider_trading", {"symbol": ticker.nse_symbol}),
        "board_meetings": client.run_action("nse_board_meetings", {"symbol": ticker.nse_symbol}),
        "financial_results": client.run_action("nse_financial_results", {"symbol": ticker.nse_symbol}),
    }
    
    keys = list(actions.keys())
    results = await asyncio.gather(*actions.values(), return_exceptions=True)
    
    data = {}
    errors = []
    
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            errors.append(f"{key}: {str(result)}")
        else:
            data[key] = result
            
    if not data and errors:
        return SourceResult(status="error", error="; ".join(errors))
        
    return SourceResult(status="ok", data=data)
