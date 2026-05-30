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

Set `ANAKIN_API_KEY` in `.env`.

## Run API

```bash
uvicorn app.main:app --reload
```

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
NSE India quote: nse_quote
Yahoo Finance quote: yf_quote
StockTwits symbol stream: st_symbol_stream
StockTwits trending: st_trending
BSE, Economic Times, Moneycontrol, SEBI: no action_id discovered yet
```

`GET /analyze/{ticker}` normalizes quote data from Yahoo/NSE and StockTwits
sentiment when those Wire calls succeed. Source modules with no discovered
action remain in the response as `missing_action`.

## Docker

```bash
docker build -t indiastocklens-backend .
docker run --env-file .env -p 8000:8000 indiastocklens-backend
```
