import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    key = settings.anakin_api_key or ""

    print(f"ANAKIN_BASE_URL={settings.anakin_base_url}")
    print(f"ANAKIN_API_KEY_present={bool(key)}")
    print(f"ANAKIN_API_KEY_starts_with_ak_dash={key.startswith('ak-')}")
    print(f"ANAKIN_API_KEY_length={len(key)}")

    if key:
        print(f"ANAKIN_API_KEY_preview={key[:3]}...{key[-4:]}")


if __name__ == "__main__":
    main()
