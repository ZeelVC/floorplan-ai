"""Command-line interface for floorplan-ai."""

from __future__ import annotations

import argparse
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process status."""
    build_parser().parse_args(argv)
    return 0
