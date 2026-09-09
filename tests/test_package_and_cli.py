"""Smoke tests for the initialized package and command-line interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class PackageAndCliTests(unittest.TestCase):
    def test_package_imports(self) -> None:
        import floorplan_ai

        self.assertEqual(floorplan_ai.__version__, "0.1.0")

    def test_module_cli_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "floorplan_ai", "--help"],
            cwd=ROOT,
            env={**__import__("os").environ, "PYTHONPATH": str(SRC)},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Indoor metric floor-plan reconstruction tooling.", result.stdout)


if __name__ == "__main__":
    unittest.main()
