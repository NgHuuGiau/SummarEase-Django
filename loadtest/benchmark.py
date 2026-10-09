#!/usr/bin/env python
"""Compatibility entry point for the evaluation management command."""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(root / "manage.py"), "evaluate", *sys.argv[1:]],
            cwd=root,
        )
    )
