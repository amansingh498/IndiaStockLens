from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedTicker:
    display: str
    nse_symbol: str
    yahoo_symbol: str
    company_name: str | None = None


def normalize_ticker(raw_ticker: str) -> ResolvedTicker:
    symbol = raw_ticker.strip().upper()
    if symbol.endswith(".NS"):
        nse_symbol = symbol[:-3]
        yahoo_symbol = symbol
    else:
        nse_symbol = symbol
        yahoo_symbol = f"{symbol}.NS"

    return ResolvedTicker(
        display=nse_symbol,
        nse_symbol=nse_symbol,
        yahoo_symbol=yahoo_symbol,
    )
