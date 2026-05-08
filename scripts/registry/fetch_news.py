"""Weekly news fetcher for slm-learning. Pulls headlines from a curated
set of feeds + APIs, writes a dated digest under `news/`.

Network-only sources (no scraping of paywalled / rate-limited pages):
  - Anthropic news (RSS-ish: HTML index parsed coarsely)
  - HuggingFace papers daily (JSON: https://huggingface.co/api/daily_papers)
  - HF Hub model search filtered to recently-updated Qwen / DeepSeek / Meta / OpenAI
  - OpenRouter `/api/v1/models` (we already query this in sync_registry.py;
    here we just diff which ids are new since last run)

Usage:
  python scripts/registry/fetch_news.py
  python scripts/registry/fetch_news.py --dry-run

Decision: slm-learning-198.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[2]
NEWS_DIR = REPO_ROOT / "news"
USER_AGENT = "slm-learning-news-fetch/0.1"

HF_DAILY_PAPERS = "https://huggingface.co/api/daily_papers"
HF_MODELS_API = "https://huggingface.co/api/models"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"

WATCH_AUTHORS = ["Qwen", "deepseek-ai", "meta-llama", "openai", "microsoft", "mistralai"]


def http_json(url: str, timeout: float = 15.0):
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"_error": str(e)[:200]}


def fetch_hf_papers(limit: int = 8) -> list[dict]:
    data = http_json(HF_DAILY_PAPERS)
    if not isinstance(data, list):
        return []
    out = []
    for item in data[:limit]:
        paper = item.get("paper") or {}
        out.append({
            "title": paper.get("title", ""),
            "id": paper.get("id", ""),
            "url": f"https://huggingface.co/papers/{paper.get('id','')}",
            "summary": (paper.get("summary") or "")[:240],
            "upvotes": paper.get("upvotes", 0),
        })
    return out


def fetch_recent_models(author: str, limit: int = 5) -> list[dict]:
    url = f"{HF_MODELS_API}?author={author}&sort=lastModified&direction=-1&limit={limit}"
    data = http_json(url)
    if not isinstance(data, list):
        return []
    return [
        {
            "id": m.get("id"),
            "last_modified": m.get("lastModified"),
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
        }
        for m in data
    ]


def fetch_openrouter_free() -> list[str]:
    data = http_json(OPENROUTER_MODELS)
    if not isinstance(data, dict) or "data" not in data:
        return []
    return sorted([m["id"] for m in data["data"] if m.get("id", "").endswith(":free")])


def render_digest(date: str) -> str:
    lines = [f"# News digest — {date}", ""]
    lines.append("## HuggingFace daily papers (top 8)")
    lines.append("")
    for p in fetch_hf_papers():
        lines.append(f"- **{p['title']}** ({p['upvotes']}↑) — {p['url']}")
        if p.get("summary"):
            lines.append(f"  {p['summary']}...")
    lines.append("")
    lines.append("## Recent model updates")
    lines.append("")
    for author in WATCH_AUTHORS:
        models = fetch_recent_models(author, limit=5)
        if not models:
            continue
        lines.append(f"### {author}")
        for m in models:
            lines.append(f"- `{m['id']}` — last modified {m['last_modified']} "
                         f"({m['downloads']} downloads, {m['likes']} likes)")
        lines.append("")
    lines.append("## OpenRouter free-tier roster")
    lines.append("")
    free = fetch_openrouter_free()
    if free:
        for fid in free:
            lines.append(f"- `{fid}`")
    else:
        lines.append("(no response)")
    lines.append("")
    lines.append("## Promotion candidates")
    lines.append("")
    lines.append("Review the items above and promote any that warrant a "
                 "registry update or decision:")
    lines.append("- Update `data/registry/datasets.json` for new datasets")
    lines.append("- Update `data/registry/model_families.json` for new models")
    lines.append("- Update `data/registry/teachers.json` if teacher policy shifts")
    lines.append("- `gad decisions add slm-learning-NNN ...` for binding decisions")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print to stdout instead of writing.")
    args = ap.parse_args(argv)

    today = dt.date.today().isoformat()
    digest = render_digest(today)
    if args.dry_run:
        print(digest)
        return 0
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = NEWS_DIR / f"{today}-digest.md"
    out_path.write_text(digest, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
