from app.models import ScoreSet, SourceResult


def build_brief(
    ticker: str,
    company: str | None,
    price: dict,
    news: list[dict],
    filings: list[dict],
    sentiment: dict,
    regulatory: list[dict],
    scores: ScoreSet,
    sources: dict[str, SourceResult],
) -> str:
    available_sources = [
        name.replace("_", " ")
        for name, result in sources.items()
        if result.status == "ok"
    ]
    source_text = ", ".join(available_sources) if available_sources else "no live sources"
    name = company or ticker

    if price:
        current = price.get("current")
        currency = price.get("currency") or "INR"
        change_percent = price.get("change_percent")
        if current is not None and change_percent is not None:
            price_text = (
                f"The latest normalized quote is {currency} {current:g}, "
                f"with a {change_percent:g}% move."
            )
        elif current is not None:
            price_text = f"The latest normalized quote is {currency} {current:g}."
        else:
            price_text = f"Live quote data was found for {ticker}."
    else:
        price_text = f"Live quote data is not available yet for {ticker}."

    sentiment_text = ""
    if sentiment:
        bullish = sentiment.get("bullish")
        bearish = sentiment.get("bearish")
        messages = sentiment.get("messages")
        if bullish is not None and bearish is not None:
            sentiment_text = (
                f" StockTwits sentiment has {bullish} bullish and {bearish} bearish "
                f"tagged message(s) across {messages or 0} recent message(s)."
            )

    analyst_text = ""
    recommendation = price.get("recommendation") if price else None
    analyst_target = price.get("analyst_target") if price else None
    if recommendation and analyst_target is not None:
        analyst_text = f" Yahoo Finance consensus shows {recommendation} with a target near {analyst_target:g}."
    elif recommendation:
        analyst_text = f" Yahoo Finance consensus shows {recommendation}."

    risk_text = "No regulatory flags were found in the current normalized dataset."
    if regulatory:
        risk_text = f"{len(regulatory)} regulatory item(s) need review."

    return (
        f"{name} currently has an IndiaStockLens score of {scores.overall}/100 "
        f"({scores.label}). {price_text} The brief is based on {source_text}. "
        f"{risk_text}{sentiment_text}{analyst_text} This is a research summary, not investment advice."
    )
