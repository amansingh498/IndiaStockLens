import asyncio
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models import AnalysisResponse, SourceResult
from app.pipeline.normalization import normalize_ticker
from app.pipeline.scoring import score_analysis
from app.pipeline.synthesis import build_brief
from app.sources.bse import fetch_bse
from app.sources.economic_times import fetch_economic_times
from app.sources.moneycontrol import fetch_moneycontrol
from app.sources.nse import fetch_nse
from app.sources.sebi import fetch_sebi
from app.sources.stocktwits import fetch_stocktwits
from app.sources.yahoo import fetch_yahoo_finance


IST = timezone(timedelta(hours=5, minutes=30), name="IST")


async def analyze_ticker(ticker: str, settings: Settings) -> AnalysisResponse:
    resolved = normalize_ticker(ticker)

    source_tasks = {
        "yahoo_finance": fetch_yahoo_finance(resolved, settings),
        "nse": fetch_nse(resolved, settings),
        "bse": fetch_bse(resolved, settings),
        "economic_times": fetch_economic_times(resolved, settings),
        "moneycontrol": fetch_moneycontrol(resolved, settings),
        "sebi": fetch_sebi(resolved, settings),
        "stocktwits": fetch_stocktwits(resolved, settings),
    }

    names = list(source_tasks)
    results = await asyncio.gather(*source_tasks.values(), return_exceptions=True)
    sources = {
        name: _coerce_source_result(result)
        for name, result in zip(names, results, strict=True)
    }

    price = _extract_price(sources)
    news = _extract_items(sources, "economic_times")
    filings = _extract_items(sources, "bse")
    sentiment = _extract_sentiment(sources)
    regulatory = _extract_items(sources, "sebi")
    scores = score_analysis(
        price=price,
        news=news,
        filings=filings,
        sentiment=sentiment,
        regulatory=regulatory,
        sources=sources,
    )
    brief = build_brief(
        ticker=resolved.display,
        company=resolved.company_name,
        price=price,
        news=news,
        filings=filings,
        sentiment=sentiment,
        regulatory=regulatory,
        scores=scores,
        sources=sources,
    )

    return AnalysisResponse(
        ticker=resolved.display,
        company=resolved.company_name,
        as_of=datetime.now(IST),
        price=price,
        news=news,
        filings=filings,
        sentiment=sentiment,
        regulatory=regulatory,
        scores=scores,
        brief=brief,
        sources=sources,
    )


def _coerce_source_result(result: object) -> SourceResult:
    if isinstance(result, SourceResult):
        return result
    if isinstance(result, TimeoutError):
        return SourceResult(status="timeout", error=str(result) or "Source timed out.")
    if isinstance(result, Exception):
        return SourceResult(status="error", error=str(result))
    return SourceResult(status="ok", data={"raw": result})


def _extract_price(sources: dict[str, SourceResult]) -> dict:
    for source_name in ("yahoo_finance", "nse"):
        source = sources.get(source_name)
        if not source or source.status != "ok" or not isinstance(source.data, dict):
            continue

        quote = _find_quote_payload(source.data.get("quote") or source.data)
        if not quote:
            continue

        quote_values = quote.get("quote") if isinstance(quote.get("quote"), dict) else quote
        stats = quote.get("stats") if isinstance(quote.get("stats"), dict) else {}
        current = _first_number(
            quote_values,
            "regularMarketPrice",
            "currentPrice",
            "lastPrice",
            "last_price",
            "ltp",
            "price",
            "close",
        )
        if current is None:
            continue

        return {
            "source": source_name,
            "current": current,
            "currency": _first_text(quote, "currency", "financialCurrency") or "INR",
            "exchange": _first_text(quote, "exchange"),
            "name": _first_text(quote, "name", "longName", "shortName"),
            "change": _first_number(quote_values, "regularMarketChange", "change", "netChange"),
            "change_percent": _change_percent(quote_values),
            "open": _first_number(quote_values, "regularMarketOpen", "open"),
            "previous_close": _first_number(quote_values, "regularMarketPreviousClose", "prev_close"),
            "day_high": _first_number(quote_values, "regularMarketDayHigh", "dayHigh", "high"),
            "day_low": _first_number(quote_values, "regularMarketDayLow", "dayLow", "low"),
            "volume": _first_number(quote_values, "regularMarketVolume", "volume"),
            "fifty_two_week_high": _first_number(
                stats,
                "fiftyTwoWeekHigh",
                "52WeekHigh",
                "52w_high",
                "yearHigh",
            ),
            "fifty_two_week_low": _first_number(
                stats,
                "fiftyTwoWeekLow",
                "52WeekLow",
                "52w_low",
                "yearLow",
            ),
            "market_cap": _first_number(quote_values, "marketCap", "market_cap"),
            "pe_ratio": _first_number(stats, "trailingPE", "forwardPE", "pe_ratio", "pe", "p_e"),
            "forward_pe": _first_number(stats, "forward_pe", "forwardPE"),
            "eps": _first_number(stats, "eps", "trailingEps"),
            "beta": _first_number(stats, "beta"),
            "book_value": _first_number(stats, "book_value", "bookValue"),
            "price_to_book": _first_number(stats, "price_to_book", "priceToBook"),
            "held_pct_institutions": _first_number(stats, "held_pct_institutions"),
            "held_pct_insiders": _first_number(stats, "held_pct_insiders"),
            "analyst_target": _first_number(stats, "analyst_target", "targetMeanPrice"),
            "recommendation": _first_text(stats, "recommendation", "recommendationKey"),
        }

    return {}


def _extract_sentiment(sources: dict[str, SourceResult]) -> dict:
    stocktwits = sources.get("stocktwits")
    if not stocktwits or stocktwits.status != "ok" or not isinstance(stocktwits.data, dict):
        return {}

    stream = stocktwits.data.get("symbol_stream")
    messages = _find_messages(stream)
    bullish = 0
    bearish = 0

    for message in messages:
        if not isinstance(message, dict):
            continue

        sentiment = message.get("sentiment")
        if isinstance(sentiment, dict):
            label = str(sentiment.get("basic") or sentiment.get("label") or "").lower()
        else:
            label = str(sentiment or "").lower()

        if "bull" in label:
            bullish += 1
        elif "bear" in label:
            bearish += 1

    tagged = bullish + bearish
    if tagged == 0:
        return {
            "source": "StockTwits",
            "messages": len(messages),
            "bullish": 0,
            "bearish": 0,
            "score": 5,
        }

    bullish_ratio = bullish / tagged
    return {
        "source": "StockTwits",
        "messages": len(messages),
        "bullish": bullish,
        "bearish": bearish,
        "bullish_ratio": round(bullish_ratio, 2),
        "score": max(0, min(10, round(bullish_ratio * 10))),
    }


def _find_messages(data: object) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("messages", "data", "results", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        nested = _find_messages(value)
        if nested:
            return nested

    return []


def _extract_items(sources: dict[str, SourceResult], source_name: str) -> list[dict]:
    source = sources.get(source_name)
    if not source or source.status != "ok":
        return []

    items = _find_list(source.data)
    return [item for item in items if isinstance(item, dict)]


def _find_list(data: object) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("items", "results", "data", "news", "filings", "orders", "notices"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        nested = _find_list(value)
        if nested:
            return nested

    return []


def _find_quote_payload(data: object) -> dict:
    if not isinstance(data, dict):
        return {}

    quote_keys = (
        "regularMarketPrice",
        "currentPrice",
        "lastPrice",
        "last_price",
        "ltp",
        "price",
    )
    if any(key in data for key in quote_keys) or isinstance(data.get("quote"), dict):
        return data

    for key in ("quote", "data", "result", "priceInfo", "info"):
        nested = _find_quote_payload(data.get(key))
        if nested:
            return nested

    for value in data.values():
        nested = _find_quote_payload(value)
        if nested:
            return nested

    return {}


def _first_number(data: dict, *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("%", "").strip()
            if cleaned:
                try:
                    return float(cleaned)
                except ValueError:
                    continue
    return None


def _first_text(data: dict, *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _change_percent(data: dict) -> float | None:
    ratio = _first_number(data, "change_pct")
    if ratio is not None:
        return ratio * 100

    return _first_number(
        data,
        "regularMarketChangePercent",
        "changePercent",
        "pChange",
        "percentChange",
    )
