"""Sync slm-learning's dataset / model_family / teacher registries against
external sources. Read-only by default; writes go through --apply.

External sources queried:
  - HuggingFace datasets-server API for `n_rows_estimate` / size hints
  - HuggingFace model-info API for `last_modified` and tag freshness
  - OpenRouter `/api/v1/models` for free-tier comparator availability
  - Anthropic / OpenAI / Google pricing pages are NOT scraped (rate-limit risk
    + brittle); update by hand on release.

Usage:
  python scripts/registry/sync_registry.py            # dry-run, prints diff
  python scripts/registry/sync_registry.py --apply    # write back

Decision: slm-learning-198.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = REPO_ROOT / "data" / "registry"
DATASETS_PATH = REGISTRY_DIR / "datasets.json"
MODEL_FAMILIES_PATH = REGISTRY_DIR / "model_families.json"
TEACHERS_PATH = REGISTRY_DIR / "teachers.json"

HF_DATASETS_API = "https://datasets-server.huggingface.co/info?dataset={hf_id}"
HF_MODEL_API = "https://huggingface.co/api/models/{hf_id}"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"

USER_AGENT = "slm-learning-registry-sync/0.1"


def http_get_json(url: str, timeout: float = 10.0) -> dict[str, Any] | None:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"_error": str(e)[:200]}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sync_datasets(reg: dict[str, Any], verbose: bool) -> list[str]:
    diffs: list[str] = []
    for entry in reg.get("datasets", []):
        hf_id = entry.get("hf_id")
        if not hf_id:
            continue
        url = HF_DATASETS_API.format(hf_id=hf_id)
        info = http_get_json(url)
        if info is None or "_error" in (info or {}):
            if verbose:
                err = (info or {}).get("_error", "no response")
                print(f"  [datasets] {hf_id}: skip ({err})")
            continue
        ds_info = info.get("dataset_info") or {}
        n_rows = None
        if isinstance(ds_info, dict):
            for split_meta in ds_info.values():
                if isinstance(split_meta, dict):
                    splits = split_meta.get("splits") or {}
                    for s in splits.values():
                        if isinstance(s, dict) and s.get("num_examples"):
                            n_rows = (n_rows or 0) + int(s["num_examples"])
        if n_rows and n_rows != entry.get("n_rows_estimate"):
            diffs.append(
                f"datasets/{entry['id']}: n_rows_estimate "
                f"{entry.get('n_rows_estimate')} -> {n_rows}"
            )
            entry["n_rows_estimate"] = n_rows
        time.sleep(0.5)
    return diffs


def sync_model_families(reg: dict[str, Any], verbose: bool) -> list[str]:
    diffs: list[str] = []
    for entry in reg.get("models", []):
        hf_id = entry.get("hf_id")
        if not hf_id:
            continue
        url = HF_MODEL_API.format(hf_id=hf_id)
        info = http_get_json(url)
        if not info or "_error" in info:
            continue
        last_modified = info.get("lastModified") or info.get("last_modified")
        if last_modified and entry.get("last_modified") != last_modified:
            diffs.append(
                f"model_families/{entry['id']}: last_modified -> {last_modified}"
            )
            entry["last_modified"] = last_modified
        time.sleep(0.5)
    return diffs


def sync_openrouter_free(reg: dict[str, Any], verbose: bool) -> list[str]:
    diffs: list[str] = []
    info = http_get_json(OPENROUTER_MODELS)
    if not info or "_error" in info:
        if verbose:
            print("  [openrouter] skip — no response")
        return diffs
    free_models: dict[str, dict] = {}
    for m in info.get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing") or {}
        if mid.endswith(":free") or (
            pricing.get("prompt") in ("0", 0, "0.0")
            and pricing.get("completion") in ("0", 0, "0.0")
        ):
            free_models[mid] = m
    for entry in reg.get("models", []):
        orid = entry.get("openrouter_id")
        if orid and orid in free_models:
            entry.setdefault("highlights", [])
            tag = "OpenRouter free-tier confirmed"
            if tag not in entry["highlights"]:
                entry["highlights"].append(tag)
                diffs.append(f"model_families/{entry['id']}: openrouter free OK")
    return diffs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Sync slm-learning registry.")
    ap.add_argument("--apply", action="store_true",
                    help="Write changes back to JSON files.")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", default="all",
                    choices=["all", "datasets", "models", "openrouter"])
    args = ap.parse_args(argv)

    datasets = load_json(DATASETS_PATH)
    models = load_json(MODEL_FAMILIES_PATH)

    diffs: list[str] = []
    if args.only in ("all", "datasets"):
        print("Syncing datasets ...")
        diffs += sync_datasets(datasets, args.verbose)
    if args.only in ("all", "models"):
        print("Syncing model families ...")
        diffs += sync_model_families(models, args.verbose)
    if args.only in ("all", "openrouter"):
        print("Syncing OpenRouter free-tier flags ...")
        diffs += sync_openrouter_free(models, args.verbose)

    print()
    print(f"== {len(diffs)} change(s) detected ==")
    for d in diffs:
        print(f"  {d}")

    if args.apply and diffs:
        save_json(DATASETS_PATH, datasets)
        save_json(MODEL_FAMILIES_PATH, models)
        print("Applied.")
    elif diffs:
        print("Run with --apply to write changes back.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
