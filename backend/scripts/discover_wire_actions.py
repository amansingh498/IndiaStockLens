import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.sources.anakin_client import AnakinWireClient


QUERIES = [
    "NSE India stock quote",
    "BSE India corporate filings",
    "Yahoo Finance stock quote",
    "Moneycontrol analyst recommendations",
    "Economic Times stock news",
    "SEBI company orders notices",
    "StockTwits sentiment",
    "Investing.com earnings calendar",
    "Groww stock peer comparison",
    "Fear and Greed market sentiment",
]


async def main() -> None:
    settings = get_settings()
    client = AnakinWireClient(settings)
    output: dict[str, object] = {}

    for query in QUERIES:
        try:
            output[query] = await client.search_actions(query)
        except Exception as exc:
            output[query] = {"error": str(exc)}

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
