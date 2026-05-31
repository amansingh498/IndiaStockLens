import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.models import AnalysisResponse, SourceResult
from app.pipeline.normalization import normalize_ticker
from app.pipeline.scoring import score_analysis
from app.pipeline.synthesis import build_brief
from app.sources.nse import fetch_nse
from app.sources.screener import fetch_screener
from app.sources.sebi import fetch_sebi
from app.sources.yahoo import fetch_yahoo_finance


IST = timezone(timedelta(hours=5, minutes=30), name="IST")
_ANALYSIS_CACHE: dict[str, tuple[float, AnalysisResponse]] = {}


async def analyze_ticker(ticker: str, settings: Settings) -> AnalysisResponse:
    resolved = normalize_ticker(ticker)
    cached = _get_cached_analysis(resolved.display, settings)
    if cached:
        return cached

    sources = await _fetch_sources_with_deadlines(resolved, settings)

    price = _extract_price(sources)
    relevance_terms = _relevance_terms(resolved.display, price)

    # News - ET/Moneycontrol not in current source set; kept for future use.
    news = _limit_items(
        _dedupe_items(
            _filter_relevant_items(
                _extract_items(sources, "economic_times") + _extract_items(sources, "moneycontrol"),
                relevance_terms,
                resolved.display,
            )
        ),
        12,
    )

    # Filings - NSE events + Screener results with per-source normalizers.
    filings = _limit_items(
        _dedupe_items(
            _filter_relevant_items(
                _extract_nse_items(sources) + _extract_screener_items(sources),
                relevance_terms,
                resolved.display,
            )
        ),
        20,
    )

    sentiment = _extract_sentiment(sources)

    # Regulatory - SEBI items with SEBI-specific normalizer.
    regulatory = _limit_items(
        _dedupe_items(
            _filter_relevant_items(
                _extract_sebi_items(sources),
                relevance_terms,
                resolved.display,
            )
        ),
        10,
    )

    public_sources = _public_sources(sources)
    scores = score_analysis(
        price=price,
        news=news,
        filings=filings,
        sentiment=sentiment,
        regulatory=regulatory,
        sources=public_sources,
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
        sources=public_sources,
    )

    response = AnalysisResponse(
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
        sources=public_sources,
    )
    _store_cached_analysis(resolved.display, response, settings)
    return response.model_copy(deep=True)


# ------------------------------------------------------------------ #
# SOURCE COERCION / PUBLIC STRIPPING                                   #
# ------------------------------------------------------------------ #

async def _fetch_sources_with_deadlines(resolved: Any, settings: Settings) -> dict[str, SourceResult]:
    source_tasks = {
        "yahoo_finance": (
            fetch_yahoo_finance(resolved, settings),
            settings.quote_source_timeout_seconds,
        ),
        "nse": (
            fetch_nse(resolved, settings),
            settings.optional_source_timeout_seconds,
        ),
        "sebi": (
            fetch_sebi(resolved, settings),
            settings.optional_source_timeout_seconds,
        ),
        "screener": (
            fetch_screener(resolved, settings),
            settings.optional_source_timeout_seconds,
        ),
    }

    async def fetch_one(name: str, coroutine: Any, timeout_seconds: float) -> tuple[str, SourceResult]:
        try:
            result = await asyncio.wait_for(coroutine, timeout=max(1.0, timeout_seconds))
        except TimeoutError:
            result = SourceResult(
                status="timeout",
                error=f"{name} exceeded {timeout_seconds:g}s source budget.",
            )
        except Exception as exc:
            result = _coerce_source_result(exc)
        return name, _coerce_source_result(result)

    tasks = [
        asyncio.create_task(fetch_one(name, coroutine, timeout_seconds))
        for name, (coroutine, timeout_seconds) in source_tasks.items()
    ]
    done, pending = await asyncio.wait(tasks, timeout=max(1.0, settings.analyze_timeout_seconds))

    sources = {
        name: SourceResult(status="timeout", error="Source did not finish before API response budget.")
        for name in source_tasks
    }
    for task in done:
        name, result = task.result()
        sources[name] = result

    for task in pending:
        task.cancel()

    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    return sources

def _get_cached_analysis(ticker: str, settings: Settings) -> AnalysisResponse | None:
    ttl = settings.cache_ttl_seconds
    if ttl <= 0:
        return None

    cached = _ANALYSIS_CACHE.get(ticker)
    if not cached:
        return None

    cached_at, response = cached
    if time.monotonic() - cached_at > ttl:
        _ANALYSIS_CACHE.pop(ticker, None)
        return None

    return response.model_copy(deep=True)


def _store_cached_analysis(ticker: str, response: AnalysisResponse, settings: Settings) -> None:
    if settings.cache_ttl_seconds <= 0:
        return
    _ANALYSIS_CACHE[ticker] = (time.monotonic(), response.model_copy(deep=True))

def _coerce_source_result(result: object) -> SourceResult:
    if isinstance(result, SourceResult):
        return result
    if isinstance(result, TimeoutError):
        return SourceResult(status="timeout", error=str(result) or "Source timed out.")
    if isinstance(result, Exception):
        return SourceResult(status="error", error=str(result))
    return SourceResult(status="ok", data={"raw": result})


def _public_sources(sources: dict[str, SourceResult]) -> dict[str, SourceResult]:
    public: dict[str, SourceResult] = {}
    for name, source in sources.items():
        data: dict[str, Any] | None = None
        if isinstance(source.data, dict):
            data = {
                "keys": [key for key in source.data.keys() if not key.startswith("_")],
            }
            counts = _source_counts(source.data)
            if counts:
                data["counts"] = counts
            errors = source.data.get("_errors")
            if isinstance(errors, list) and errors:
                data["partial_errors"] = errors[:3]
        elif isinstance(source.data, list):
            data = {"count": len(source.data)}

        public[name] = SourceResult(status=source.status, data=data, error=source.error)
    return public


# ------------------------------------------------------------------ #
# PRICE EXTRACTION                                                     #
# ------------------------------------------------------------------ #

def _extract_price(sources: dict[str, SourceResult]) -> dict:
    for source_name in ("yahoo_finance",):
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
    return {}


# ------------------------------------------------------------------ #
# PER-SOURCE ITEM EXTRACTORS                                           #
# ------------------------------------------------------------------ #

def _extract_nse_items(sources: dict[str, SourceResult]) -> list[dict]:
    """Extract and normalize all NSE sub-source items."""
    source = sources.get("nse")
    if not source or source.status != "ok" or not isinstance(source.data, dict):
        return []

    items: list[dict] = []

    ca_data = source.data.get("corporate_actions")
    if ca_data is not None:
        for raw in _find_lists(ca_data, exclude_keys=set()):
            if isinstance(raw, dict):
                items.append(_normalize_nse_corporate_action(raw))

    it_data = source.data.get("insider_trading")
    if it_data is not None:
        for raw in _find_lists(it_data, exclude_keys=set()):
            if isinstance(raw, dict):
                items.append(_normalize_nse_insider(raw))

    bm_data = source.data.get("board_meetings")
    if bm_data is not None:
        for raw in _find_lists(bm_data, exclude_keys=set()):
            if isinstance(raw, dict):
                items.append(_normalize_nse_board_meeting(raw))

    return [i for i in items if i]


def _extract_sebi_items(sources: dict[str, SourceResult]) -> list[dict]:
    """Extract and normalize all SEBI regulatory items."""
    source = sources.get("sebi")
    if not source or source.status != "ok" or not isinstance(source.data, dict):
        return []

    items: list[dict] = []
    latest_data = source.data.get("latest")
    if latest_data is not None:
        for raw in _find_lists(latest_data, exclude_keys=set()):
            if isinstance(raw, dict):
                items.append(_normalize_sebi_item(raw))

    return [i for i in items if i]


def _extract_screener_items(sources: dict[str, SourceResult]) -> list[dict]:
    """Extract and normalize Screener quarterly and overview items."""
    source = sources.get("screener")
    if not source or source.status != "ok" or not isinstance(source.data, dict):
        return []

    items: list[dict] = []

    q_data = source.data.get("quarterly")
    if q_data is not None:
        for raw in _find_lists(q_data, exclude_keys=set()):
            if isinstance(raw, dict):
                items.append(_normalize_screener_quarterly(raw))

    ov_data = source.data.get("overview")
    if isinstance(ov_data, dict):
        item = _normalize_screener_overview(ov_data)
        if item:
            items.append(item)
    elif isinstance(ov_data, list):
        for raw in ov_data:
            if isinstance(raw, dict):
                item = _normalize_screener_overview(raw)
                if item:
                    items.append(item)

    return [i for i in items if i]


# ------------------------------------------------------------------ #
# PER-SOURCE NORMALIZERS                                               #
# Each returns a dict with: source, type, title, date, detail, link,   #
# symbol, tags, and optional severity. Unknown keys are skipped.       #
# ------------------------------------------------------------------ #

def _normalize_nse_corporate_action(item: dict) -> dict:
    symbol = _first_text(item, "symbol", "Symbol")
    purpose = _first_text(item, "subject", "purpose", "Purpose", "desc")
    ex_date = _first_text(item, "exDate", "ex_date", "exdate", "Ex Date", "bcStartDate")
    rec_date = _first_text(item, "recDate", "record_date", "recordDate")
    face_val = _first_text(item, "faceVal", "face_value", "faceValue", "facevalue")
    series = _first_text(item, "series", "Series")

    title = purpose or "Corporate Action"

    detail_parts: list[str] = []
    if ex_date:
        detail_parts.append(f"Ex date: {ex_date}")
    if rec_date:
        detail_parts.append(f"Record: {rec_date}")
    if face_val:
        detail_parts.append(f"FV: Rs {face_val}")

    tags = ["corporate-action"]
    if purpose:
        p = purpose.lower()
        if "dividend" in p:
            tags = ["dividend"]
        elif "split" in p:
            tags = ["stock-split"]
        elif "bonus" in p:
            tags = ["bonus"]
        elif "rights" in p:
            tags = ["rights-issue"]
        elif "buyback" in p or "buy back" in p:
            tags = ["buyback"]
    if series and series not in tags:
        tags.append(series)

    return {
        "source": "nse",
        "type": "corporate_action",
        "title": title,
        "date": ex_date,
        "detail": " | ".join(detail_parts) or None,
        "link": _first_text(item, "url", "link"),
        "symbol": symbol,
        "tags": tags,
    }


def _normalize_nse_insider(item: dict) -> dict:
    symbol = _first_text(item, "symbol", "Symbol")
    name = _first_text(item, "name", "acquirerName", "acqName", "personName", "person")
    date = _first_text(item, "date", "acqfromDt", "from_date", "fromDate")
    sec_type = _first_text(item, "secType", "typeOfSecurity", "security_type", "securityType")
    acq_mode = _first_text(item, "acqMode", "acq_mode", "mode", "Mode")
    after_pct = _first_number(item, "afterAcqSharesPerc", "after_pct", "afterPct", "afterAcqPer")
    sec_acq = _first_number(item, "secAcq", "noOfShareAcq", "shares_acquired", "sharesAcquired")

    mode_label = (acq_mode or "").replace("_", " ").title() if acq_mode else "Trade"
    title = f"{name or 'Insider'} - {mode_label}"

    detail_parts: list[str] = []
    if sec_acq is not None:
        detail_parts.append(f"{int(sec_acq):,} shares")
    if after_pct is not None:
        detail_parts.append(f"{after_pct:.2f}% post-trade holding")
    if sec_type:
        detail_parts.append(sec_type)

    return {
        "source": "nse",
        "type": "insider_trade",
        "title": title,
        "date": date,
        "detail": " | ".join(detail_parts) or None,
        "link": _first_text(item, "url", "link"),
        "symbol": symbol,
        "tags": ["insider-trade"],
    }


def _normalize_nse_board_meeting(item: dict) -> dict:
    symbol = _first_text(item, "symbol", "sym")
    purpose = _first_text(item, "purpose", "Purpose", "agenda")
    bm_date = _first_text(item, "bm_date", "meeting_date", "date", "meetingDate", "bmDate")
    desc = _first_text(item, "bm_desc", "description", "details", "bmDesc")

    title = purpose or desc or "Board Meeting"
    detail = desc if (desc and desc != title) else None

    return {
        "source": "nse",
        "type": "board_meeting",
        "title": title,
        "date": bm_date,
        "detail": detail,
        "link": _first_text(item, "url", "link"),
        "symbol": symbol,
        "tags": ["board-meeting"],
    }


def _normalize_sebi_item(item: dict) -> dict:
    title = _first_text(item, "title", "headline", "subject", "order_title", "orderTitle")
    date = _first_text(item, "order_date", "date", "published", "filing_date", "orderDate")
    entity = _first_text(item, "entity_name", "company", "respondent", "entityName", "name")
    category = _first_text(item, "category", "order_type", "orderType", "type")
    link = _first_text(item, "pdf_url", "url", "link", "document_url", "pdfUrl")

    detail_parts: list[str] = []
    if entity:
        detail_parts.append(entity)
    if category:
        detail_parts.append(category.replace("_", " ").title())

    tags = ["sebi"]
    severity = "medium"
    if category:
        c = category.lower()
        if any(word in c for word in ("penalty", "fine", "adjudication", "settlement")):
            tags = ["sebi-penalty"]
            severity = "high"
        elif "order" in c:
            tags = ["sebi-order"]
            severity = "high"
        elif "notice" in c:
            tags = ["sebi-notice"]
            severity = "medium"
        elif "circular" in c:
            tags = ["sebi-circular"]
            severity = "low"

    combined_text = " ".join(str(value) for value in (title, entity, category) if value).lower()
    if any(word in combined_text for word in ("penalty", "fraud", "ban", "debar", "violation")):
        severity = "high"
    elif any(word in combined_text for word in ("warning", "notice", "show cause")):
        severity = "medium"

    return {
        "source": "sebi",
        "type": "regulatory",
        "title": title or "SEBI Regulatory Item",
        "date": date,
        "detail": " | ".join(detail_parts) or None,
        "link": link,
        "symbol": None,
        "tags": tags,
        "severity": severity,
    }


def _normalize_screener_quarterly(item: dict) -> dict:
    quarter = _first_text(item, "quarter", "Quarter", "period", "Period")
    year = _first_text(item, "financial_year", "year", "fy", "FY")

    revenue = _first_number(item, "revenue", "Revenue", "sales", "Sales", "net_sales", "netSales")
    profit = _first_number(item, "profit", "Profit", "net_profit", "PAT", "pat", "netProfit")
    eps = _first_number(item, "eps", "EPS", "diluted_eps", "dilutedEps")

    label = quarter or "Quarter"
    if year:
        label = f"{label} {year}"

    detail_parts: list[str] = []
    if revenue is not None:
        detail_parts.append(f"Rev Rs {revenue:,.0f}Cr")
    if profit is not None:
        detail_parts.append(f"PAT Rs {profit:,.0f}Cr")
    if eps is not None:
        detail_parts.append(f"EPS Rs {eps:.2f}")

    tags = ["quarterly"]
    if quarter:
        tags.append(quarter.replace(" ", "-").lower())

    return {
        "source": "screener",
        "type": "quarterly",
        "title": f"{label} Financial Results",
        "date": _first_text(item, "filing_date", "date", "result_date", "resultDate"),
        "detail": " | ".join(detail_parts) or None,
        "link": _first_text(item, "xbrl_link", "url", "link"),
        "symbol": _first_text(item, "symbol", "Symbol"),
        "tags": tags,
    }


def _normalize_screener_overview(item: dict) -> dict:
    company = _first_text(item, "name", "company", "company_name", "companyName")
    sector = _first_text(item, "sector", "Sector", "industry", "Industry")

    if not company and not sector:
        return {}

    pe = _first_number(item, "pe", "PE", "pe_ratio", "price_earnings", "priceEarnings")
    promoter_pct = _first_number(
        item, "promoter_holding", "promoterHolding", "promoter_pct", "promoterPct"
    )

    detail_parts: list[str] = []
    if sector:
        detail_parts.append(sector)
    if pe is not None:
        detail_parts.append(f"PE {pe:.1f}x")
    if promoter_pct is not None:
        detail_parts.append(f"Promoter {promoter_pct:.1f}%")

    return {
        "source": "screener",
        "type": "overview",
        "title": f"Company Overview - {company or sector}",
        "date": None,
        "detail": " | ".join(detail_parts) or None,
        "link": _first_text(item, "url", "link"),
        "symbol": _first_text(item, "symbol", "ticker"),
        "tags": ["overview"],
    }


def _normalize_generic(item: dict, source_name: str) -> dict:
    """Fallback normalizer for sources without a specific handler."""
    return {
        "source": source_name,
        "type": "filing",
        "title": _first_text(item, "title", "headline", "subject", "purpose", "name") or "Item",
        "date": _first_text(item, "date", "published", "filing_date", "from_date"),
        "detail": None,
        "link": _first_text(item, "url", "link", "xbrl_link", "pdf_url"),
        "symbol": _first_text(item, "symbol"),
        "tags": [],
    }


# ------------------------------------------------------------------ #
# LEGACY GENERIC EXTRACTOR (kept for news sources)                    #
# ------------------------------------------------------------------ #

def _extract_items(
    sources: dict[str, SourceResult],
    source_name: str,
    exclude_keys: set[str] | None = None,
) -> list[dict]:
    source = sources.get(source_name)
    if not source or source.status != "ok":
        return []

    items = _find_lists(source.data, exclude_keys=exclude_keys or set())
    return [_clean_item(item, source_name) for item in items if isinstance(item, dict)]


def _clean_item(item: dict, source_name: str) -> dict:
    kept_keys = (
        "title",
        "headline",
        "subject",
        "purpose",
        "type",
        "category",
        "symbol",
        "company",
        "company_name",
        "name",
        "url",
        "link",
        "published",
        "date",
        "filing_date",
        "from_date",
        "to_date",
        "quarter",
        "period",
        "financial_year",
        "xbrl_link",
    )
    cleaned = {key: item[key] for key in kept_keys if key in item and item[key] not in (None, "")}
    cleaned = cleaned or item
    return {"source": source_name.replace("_", " "), **cleaned}


# ------------------------------------------------------------------ #
# RELEVANCE FILTERING / DEDUP / LIMIT                                  #
# ------------------------------------------------------------------ #

def _relevance_terms(ticker: str, price: dict) -> set[str]:
    terms = {ticker.upper()}
    name = price.get("name")
    if isinstance(name, str):
        normalized_name = name.upper()
        terms.add(normalized_name)
        words = [
            word
            for word in normalized_name.replace("&", " ").split()
            if len(word) >= 4 and word not in {"LIMITED", "INDUSTRIES", "INDIA"}
        ]
        if words:
            terms.add(words[0])
        if len(words) >= 2:
            terms.add(" ".join(words[:2]))
    return terms


def _filter_relevant_items(items: list[dict], terms: set[str], ticker: str) -> list[dict]:
    relevant: list[dict] = []
    ticker_upper = ticker.upper()
    for item in items:
        symbol = item.get("symbol")
        if isinstance(symbol, str):
            if symbol.upper() == ticker_upper:
                relevant.append(item)
            continue

        text = " ".join(
            str(value) for value in item.values()
            if isinstance(value, str)
        ).upper()
        if any(term and term in text for term in terms):
            relevant.append(item)
    return relevant


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in items:
        key = _item_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _item_key(item: dict) -> str:
    # Check unified link field first, then legacy field names
    for key in ("link", "url", "xbrl_link"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value.strip().lower()
    for key in ("title", "headline", "subject", "purpose"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value.strip().lower()
    return repr(sorted((k, v) for k, v in item.items() if isinstance(v, (str, int, float))))


def _limit_items(items: list[dict], limit: int) -> list[dict]:
    return items[:limit]


# ------------------------------------------------------------------ #
# STRUCTURAL HELPERS                                                   #
# ------------------------------------------------------------------ #

def _find_lists(data: object, exclude_keys: set[str]) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    list_keys = {
        "items",
        "results",
        "data",
        "news",
        "filings",
        "orders",
        "notices",
        "records",
        "corporateActions",
        "corporate_actions",
        "insiderTrading",
        "insider_trading",
        "boardMeetings",
        "board_meetings",
        "quarterly",
    }
    items: list = []
    for key, value in data.items():
        if key in exclude_keys or key.startswith("_"):
            continue
        if isinstance(value, list):
            if key in list_keys or all(isinstance(row, dict) for row in value[:5]):
                items.extend(value)
            continue
        if isinstance(value, dict):
            nested = _find_lists(value, exclude_keys)
            if nested:
                items.extend(nested)

    return items


def _source_counts(data: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            counts[key] = len(value)
        elif isinstance(value, dict):
            counts[key] = len(_find_lists(value, exclude_keys=set()))
    return {key: count for key, count in counts.items() if count}


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


def _first_number_deep(data: object, *keys: str) -> float | None:
    if isinstance(data, dict):
        value = _first_number(data, *keys)
        if value is not None:
            return value
        for nested in data.values():
            value = _first_number_deep(nested, *keys)
            if value is not None:
                return value
    elif isinstance(data, list):
        for nested in data:
            value = _first_number_deep(nested, *keys)
            if value is not None:
                return value
    return None


def _first_text_deep(data: object, *keys: str) -> str | None:
    if isinstance(data, dict):
        value = _first_text(data, *keys)
        if value is not None:
            return value
        for nested in data.values():
            value = _first_text_deep(nested, *keys)
            if value is not None:
                return value
    elif isinstance(data, list):
        for nested in data:
            value = _first_text_deep(nested, *keys)
            if value is not None:
                return value
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
