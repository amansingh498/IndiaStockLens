# IndiaStockLens Backend

Backend-first data pipeline for the Anakin.io hackathon project.

## Local setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `ANAKIN_API_KEY` in `.env` for a single key, or set `ANAKIN_API_KEYS` to a
comma-separated list when multiple keys are available. The Wire client rotates
across the configured keys and keeps each key below `ANAKIN_REQUESTS_PER_MINUTE`
(default: `25`) to reduce credit pressure and leave headroom under rate limits.

## Run API

```bash
uvicorn app.main:app --reload
```

`GET /analyze/{ticker}` calls the live backend pipeline and should be used in
production. The saved fixture flow was removed so the deployed app always uses
live API responses.

Endpoints:

```text
GET /health
GET /analyze/{ticker}
```

## Discover Wire actions

```bash
python scripts/discover_wire_actions.py
```

Use the discovered `action_id` values to replace placeholder source modules.

Current Wire action coverage:

```text
Yahoo Finance quote: yf_quote
NSE: nse_corporate_actions, nse_insider_trading, nse_board_meetings
SEBI: sebi_latest
Screener: scr_company_overview, scr_company_quarterly
```

`GET /analyze/{ticker}` normalizes quote data from Yahoo Finance and combines it
with NSE company events, SEBI watch items, and Screener fundamentals when their
Wire calls succeed. Broad news, BSE corporate actions, NSE financial results,
market-wide sentiment, Screener peers, and StockTwits are not called by default
to avoid duplicate data and unnecessary credit usage.

## Docker

```bash
docker build -t indiastocklens-backend .
docker run --env-file .env -p 8000:8000 indiastocklens-backend
```
