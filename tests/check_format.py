"""Run pinned Python and native source style checks."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

subprocess.run([sys.executable, "-m", "ruff", "check", "."], cwd=ROOT, check=True)
subprocess.run([sys.executable, "-m", "ruff", "format", "--check", "."], cwd=ROOT, check=True)
sources = subprocess.check_output(
    ["git", "ls-files", "*.cpp", "*.hpp", "*.h", "*.c"], cwd=ROOT, text=True
).splitlines()
subprocess.run(["clang-format", "--dry-run", "--Werror", *sources], cwd=ROOT, check=True)
