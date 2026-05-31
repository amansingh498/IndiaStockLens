"""
Score semantics for IndiaStockLens.

Primary axes, each scored 0-10:

  data_confidence            source completeness and reliability
  investment_attractiveness  fundamentals, valuation, and analyst stance
  regulatory_risk            regulatory/governance safety; higher is safer

Overall (0-100):
  overall = round(confidence * 2 + attractiveness * 5 + reg_risk * 3)

Weights: 20% confidence, 50% attractiveness, 30% regulatory safety.
Source availability contributes to confidence, but strong overall scores still
require actual valuation/fundamental quality and a clean regulatory picture.
"""

from app.models import ScoreSet, SourceResult


def score_analysis(
    price: dict,
    news: list[dict],
    filings: list[dict],
    sentiment: dict,
    regulatory: list[dict],
    sources: dict[str, SourceResult],
) -> ScoreSet:
    ok_sources = {name for name, result in sources.items() if result.status == "ok"}
    partial_error_count = sum(
        len(result.data.get("partial_errors", []))
        for result in sources.values()
        if isinstance(result.data, dict)
    )

    confidence_weights = {
        "yahoo_finance": 3,
        "nse": 2,
        "sebi": 2,
        "screener": 2,
    }
    data_confidence = 1 + sum(weight for name, weight in confidence_weights.items() if name in ok_sources)
    if price:
        data_confidence += 1
    if filings:
        data_confidence += 1
    if regulatory:
        data_confidence += 1
    data_confidence -= min(2, partial_error_count)
    data_confidence = max(0, min(10, data_confidence))

    attractiveness = 4

    pe_ratio = price.get("pe_ratio") if price else None
    price_to_book = price.get("price_to_book") if price else None
    analyst_target = price.get("analyst_target") if price else None
    current_price = price.get("current") if price else None
    recommendation = (price.get("recommendation") or "").lower() if price else ""
    held_pct_institutions = price.get("held_pct_institutions") if price else None

    if isinstance(pe_ratio, int | float):
        if 0 < pe_ratio <= 25:
            attractiveness += 2
        elif 0 < pe_ratio <= 40:
            attractiveness += 1
        elif pe_ratio > 60 or pe_ratio < 0:
            attractiveness -= 2

    if isinstance(price_to_book, int | float):
        if price_to_book <= 2.5:
            attractiveness += 1
        elif price_to_book > 5:
            attractiveness -= 1

    if any(keyword in recommendation for keyword in ("strong_buy", "strongbuy")):
        attractiveness += 2
    elif "buy" in recommendation:
        attractiveness += 1
    elif any(keyword in recommendation for keyword in ("sell", "underperform", "underweight")):
        attractiveness -= 1

    if isinstance(analyst_target, int | float) and isinstance(current_price, int | float) and current_price > 0:
        upside_pct = (analyst_target - current_price) / current_price * 100
        if upside_pct > 20:
            attractiveness += 1
        elif upside_pct < -5:
            attractiveness -= 1

    if isinstance(held_pct_institutions, int | float) and held_pct_institutions >= 0.30:
        attractiveness += 1

    screener_items = [item for item in filings if item.get("source") == "screener"]
    quarterly_items = [item for item in screener_items if item.get("type") == "quarterly"]
    overview_items = [item for item in screener_items if item.get("type") == "overview"]
    if quarterly_items:
        attractiveness += 1
    if overview_items:
        attractiveness += 1

    attractiveness = max(0, min(10, attractiveness))

    reg_risk = 7 if price else 5
    severity_penalty = 0
    for item in regulatory:
        severity = str(item.get("severity") or "").lower()
        if severity == "high":
            severity_penalty += 2
        elif severity == "medium":
            severity_penalty += 1
        elif severity:
            severity_penalty += 0
        else:
            severity_penalty += 1
    reg_risk -= min(5, severity_penalty)

    held_pct_insiders = price.get("held_pct_insiders") if price else None
    if isinstance(held_pct_insiders, int | float) and held_pct_insiders > 0.75:
        reg_risk -= 1

    if "nse" not in ok_sources:
        reg_risk -= 1
    if "sebi" not in ok_sources:
        reg_risk -= 2
    if partial_error_count:
        reg_risk -= 1

    reg_risk = max(0, min(10, reg_risk))

    fundamentals = 4
    if price:
        fundamentals += 1
    if quarterly_items:
        fundamentals += min(2, len(quarterly_items))
    if overview_items:
        fundamentals += 1
    if isinstance(pe_ratio, int | float):
        if 0 < pe_ratio <= 25:
            fundamentals += 2
        elif pe_ratio > 60:
            fundamentals -= 1
    fundamentals = max(0, min(10, fundamentals))

    technicals = 6 if price else 4
    change_percent = price.get("change_percent") if price else None
    if isinstance(change_percent, int | float):
        if change_percent >= 2:
            technicals = 7
        elif change_percent <= -2:
            technicals = 5
    technicals = max(0, min(10, technicals))

    sentiment_score = 5 if not sentiment else int(sentiment.get("score", 5))
    sentiment_score = max(0, min(10, sentiment_score))

    if isinstance(held_pct_institutions, int | float):
        institutional_trust = 8 if held_pct_institutions >= 0.25 else 6
    else:
        institutional_trust = 5

    overall = max(
        0,
        min(
            100,
            round(data_confidence * 2 + attractiveness * 5 + reg_risk * 3),
        ),
    )

    if overall >= 75:
        label = "Strong"
    elif overall >= 55:
        label = "Watch"
    else:
        label = "Caution"

    return ScoreSet(
        data_confidence=data_confidence,
        investment_attractiveness=attractiveness,
        regulatory_risk=reg_risk,
        fundamentals=fundamentals,
        technicals=technicals,
        sentiment=sentiment_score,
        institutional_trust=institutional_trust,
        overall=overall,
        label=label,
    )
