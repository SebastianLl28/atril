"""Loads `.env` into os.environ before the modules read their ATRIL_* variables.

Looked up in the current directory, then in the repo root. Variables already set in the
real environment win over the file.
"""

import os
from pathlib import Path


def load_env():
    for folder in (Path.cwd(), Path(__file__).resolve().parents[2]):
        path = folder / ".env"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        return


load_env()
