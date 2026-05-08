"""Tiny .env loader (no python-dotenv dep). Load before importing scripts that need API keys.

Usage in another script:
    from _load_env import load_env
    load_env()  # reads ../../.env relative to this file (repo root)
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path | None = None) -> int:
    """Load KEY=VALUE pairs from .env into os.environ. Returns count loaded."""
    if path is None:
        # Default: repo root .env (../../ from scripts/eval/)
        path = Path(__file__).resolve().parents[2] / ".env"
    p = Path(path)
    if not p.is_file():
        return 0
    n = 0
    # encoding="utf-8-sig" strips the BOM if present (PowerShell's Set-Content
    # writes UTF-8 with BOM by default on Windows)
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Override if missing OR currently empty (an empty env var should be
        # treated the same as unset for API-key resolution purposes)
        if key and (key not in os.environ or not os.environ[key]):
            os.environ[key] = value
            n += 1
    return n


if __name__ == "__main__":
    loaded = load_env()
    print(f"loaded {loaded} env vars from .env")
    for k in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "HF_TOKEN"):
        v = os.environ.get(k, "")
        present = "set" if v else "unset"
        print(f"  {k}: {present} (len={len(v)})")
