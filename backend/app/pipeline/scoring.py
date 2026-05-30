from app.models import ScoreSet, SourceResult


def score_analysis(
    price: dict,
    news: list[dict],
    filings: list[dict],
    sentiment: dict,
    regulatory: list[dict],
    sources: dict[str, SourceResult],
) -> ScoreSet:
    source_ok_count = sum(1 for result in sources.values() if result.status == "ok")

    technicals = 6 if price else 4
    change_percent = price.get("change_percent")
    if isinstance(change_percent, int | float):
        if change_percent >= 2:
            technicals = 7
        elif change_percent <= -2:
            technicals = 5

    sentiment_score = 5 if not sentiment else int(sentiment.get("score", 5))
    regulatory_risk = 8 if not regulatory else 4
    institutional_holding = price.get("held_pct_institutions")
    if isinstance(institutional_holding, int | float):
        institutional_trust = 8 if institutional_holding >= 0.25 else 6
    else:
        institutional_trust = 5

    pe_ratio = price.get("pe_ratio")
    fundamentals = 5 + min(len(filings), 3)
    if isinstance(pe_ratio, int | float):
        if 0 < pe_ratio <= 25:
            fundamentals += 2
        elif pe_ratio > 60:
            fundamentals -= 1
    fundamentals = max(0, min(10, fundamentals))

    raw_total = (
        fundamentals * 1.5
        + technicals * 1.5
        + sentiment_score
        + regulatory_risk * 1.5
        + institutional_trust
        + min(source_ok_count, 5) * 2
    )
    confidence_penalty = 0.45 if source_ok_count == 0 else 1.0
    overall = max(0, min(100, int(raw_total * 2.0 * confidence_penalty)))

    if overall >= 75:
        label = "Strong"
    elif overall >= 55:
        label = "Watch"
    else:
        label = "Caution"

    return ScoreSet(
        fundamentals=fundamentals,
        technicals=technicals,
        sentiment=sentiment_score,
        regulatory_risk=regulatory_risk,
        institutional_trust=institutional_trust,
        overall=overall,
        label=label,
    )
