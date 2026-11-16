"""Model/capability report for the next implementation step.

This does not call paid providers. It prints the catalogue, key presence and the
demo pipeline status. Once the Ark/Kling/MiniMax adapters land, this script is
where the 3-script x 4-model bake-off will be recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adstudio import params  # noqa: E402


def main() -> None:
    rows = []
    for model in params.catalog():
        rows.append({
            "id": model["id"],
            "provider": model["provider"],
            "native_audio": model["native_audio"],
            "key_present": model["key_present"],
            "available": model["available"],
            "reason": model["reason"],
        })
    print(json.dumps({"models": rows, "demo_available": any(r["id"] == "demo" for r in rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
