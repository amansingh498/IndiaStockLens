import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.pipeline.analyzer import analyze_ticker


async def main() -> None:
    args = [arg for arg in sys.argv[1:] if arg]
    summary = "--summary" in args
    output_path = _output_path(args)
    ticker_args = [
        arg
        for index, arg in enumerate(args)
        if arg != "--summary"
        and arg != "--output"
        and (index == 0 or args[index - 1] != "--output")
    ]
    ticker = ticker_args[0] if ticker_args else "RELIANCE"
    result = await analyze_ticker(ticker, get_settings())
    if summary:
        payload = result.model_dump(mode="json", exclude={"sources"})
        payload["source_status"] = {
            name: {
                "status": source.status,
                "error": source.error[:240] if source.error else None,
                "top_level_keys": list(source.data) if isinstance(source.data, dict) else None,
                "item_count": len(source.data) if isinstance(source.data, list) else None,
            }
            for name, source in result.sources.items()
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        payload = result.model_dump(mode="json")
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Saved analysis fixture to {output_path}")
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=True))


def _output_path(args: list[str]) -> Path | None:
    if "--output" not in args:
        return None

    index = args.index("--output")
    if index + 1 >= len(args):
        raise ValueError("--output requires a file path.")
    return Path(args[index + 1])


if __name__ == "__main__":
    asyncio.run(main())
