"""Command-line interface for floorplan-ai."""

from __future__ import annotations

import argparse
from pathlib import Path
from floorplan_ai.dataset.models import CaptureInput
from collections.abc import Sequence

from floorplan_ai import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level command-line parser."""
    parser = argparse.ArgumentParser(
        prog="floorplan-ai",
        description="Indoor metric floor-plan reconstruction tooling.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")
    for command in ("perceive-photo", "perceive-video", "perceive"):
        sub = subparsers.add_parser(command); sub.add_argument("--input", required=True); sub.add_argument("--output", required=True)
        if command == "perceive": sub.add_argument("--source", choices=("auto", "photo", "video"), default="auto")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process status."""
    args = build_parser().parse_args(argv)
    if not args.command: return 0
    source = getattr(args, "source", "") or ("photo" if args.command == "perceive-photo" else "video")
    input_path = Path(args.input); output = Path(args.output)
    if source == "auto": source = "video" if input_path.is_file() and input_path.suffix.lower() in {".mp4", ".mov", ".avi", ".m4v"} else "photo"
    try:
        from floorplan_ai.frontend import reconstruct_photos, reconstruct_video
        if source == "photo":
            paths = sorted(p for p in (input_path.iterdir() if input_path.is_dir() else (input_path,)) if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
            reconstruct_photos(tuple(CaptureInput(capture_id=f"photo-{i}", source_type="photo", file=p.name, resolved_file=p) for i,p in enumerate(paths)), output)
        else: reconstruct_video(CaptureInput(capture_id="video",source_type="video",file=input_path.name,resolved_file=input_path),output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0
