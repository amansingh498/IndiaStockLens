import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.pipeline.analyzer import analyze_ticker


async def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    result = await analyze_ticker(ticker, get_settings())
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
