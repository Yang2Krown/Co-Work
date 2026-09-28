"""Small dependency-free loader for the repository-local ``.env`` file."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_dotenv(path: Optional[Path] = None) -> Optional[Path]:
    """Load missing variables from ``.env`` without overriding real environment."""

    env_path = path or Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return None
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not _KEY.fullmatch(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return env_path


__all__ = ["load_dotenv"]
