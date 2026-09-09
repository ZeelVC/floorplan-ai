"""Validate locally acquired model assets for the offline-first pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_models(model_dir: Path = Path("models")) -> list[str]:
    """Return declared model filenames that are missing from *model_dir*."""
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "models" / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"model manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    return [
        model["filename"]
        for model in manifest["models"]
        if not (Path(model_dir) / model["filename"]).is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate locally acquired model assets.")
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    missing = validate_models(args.model_dir)
    if missing:
        print(
            "Missing local model assets: "
            + ", ".join(missing)
            + "\nAcquire them during setup; this command never downloads automatically."
        )
        return 1 if args.check else 0

    print("All declared local model assets are present.")
    return 0
