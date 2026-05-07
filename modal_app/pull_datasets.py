"""Modal app — pull external datasets into a remote volume, NEVER local.

Per slm-learning-105 (hardware policy): anything >100MB lives on a
Modal volume. The user's laptop is at 93% disk; we don't touch it.

Datasets pulled (initial set):

  bigcode/the-stack-smol-xs    ~120 MB Python  — code corpus seed
  Anthropic/hh-rlhf            ~80 MB          — DPO preference pairs
  OpenAssistant/oasst2         ~200 MB         — multi-turn assistant
  princeton-nlp/SWE-bench (verified subset)    — coder eval gold

Volume layout:

  slm-data/external/the-stack-smol-xs/
  slm-data/external/hh-rlhf/
  slm-data/external/oasst2/
  slm-data/external/swebench-verified/
  slm-data/external/MANIFEST.json   (provenance + sha256 + counts)

Usage

    modal run modal_app/pull_datasets.py             # all datasets
    modal run modal_app/pull_datasets.py::pull_one   # one specific dataset

Decision refs: slm-learning-105 (hardware policy), slm-learning-094
(composition strategy), 097 (3-artifact rule -> external corpora are
artifact-track inputs).
"""
from __future__ import annotations

import modal


app = modal.App("slm-learning-pull-datasets")

image = (
    modal.Image.debian_slim()
    .pip_install(
        "datasets>=3.0",
        "huggingface_hub>=0.30",
        "pyarrow",
    )
)

volume = modal.Volume.from_name("slm-data", create_if_missing=True)
VOLUME_MOUNT = "/data"


# Manifest of datasets to pull. Each entry:
#   id:        HF dataset id
#   subset:    optional config_name
#   split:     usually train / test / validation
#   limit:     cap rows (None = full)
#   target:    subdir under /data/external/
#   format:    parquet / jsonl
DATASETS = [
    # Replaced bigcode/the-stack-smol (gated) with public OpenCodeReasoning
    # 736k pairs of reasoning-augmented code — stronger signal for our
    # coder shot than raw code (it has explanation + chain-of-thought
    # baked in).
    {
        "id": "nvidia/OpenCodeReasoning",
        "subset": "split_0",
        "split": "split_0",
        "limit": 30000,
        "target": "open-code-reasoning",
        "format": "parquet",
    },
    {
        "id": "Anthropic/hh-rlhf",
        "subset": None,
        "split": "train",
        "limit": 50000,
        "target": "hh-rlhf",
        "format": "parquet",
    },
    {
        "id": "OpenAssistant/oasst2",
        "subset": None,
        "split": "train",
        "limit": 50000,
        "target": "oasst2",
        "format": "parquet",
    },
    {
        "id": "princeton-nlp/SWE-bench_Verified",
        "subset": None,
        "split": "test",
        "limit": None,
        "target": "swebench-verified",
        "format": "parquet",
    },
    # bigcode/starcoderdata is also gated; alternative public code corpora
    # for future pulls: codeparrot/github-code (large), code_contests
    # (DeepMind), code_x_glue_cc_code_completion_token. We can swap these
    # in once the OpenCodeReasoning pull validates the pipeline.
]


@app.function(
    image=image,
    volumes={VOLUME_MOUNT: volume},
    timeout=3600,
    cpu=4,
    memory=8192,
)
def pull_one(spec: dict) -> dict:
    import hashlib
    import json
    import os
    import time
    from pathlib import Path

    from datasets import load_dataset

    target_dir = Path(VOLUME_MOUNT) / "external" / spec["target"]
    target_dir.mkdir(parents=True, exist_ok=True)

    out_path = target_dir / f"data.{spec['format']}"
    info: dict = {
        "id": spec["id"],
        "subset": spec.get("subset"),
        "split": spec["split"],
        "limit": spec.get("limit"),
        "target": spec["target"],
    }

    if out_path.exists() and out_path.stat().st_size > 0:
        info["status"] = "already_present"
        info["bytes"] = out_path.stat().st_size
        info["path"] = str(out_path)
        return info

    print(f"[pull] {spec['id']} (subset={spec.get('subset')}, split={spec['split']}, limit={spec.get('limit')})")
    t0 = time.time()
    try:
        if spec.get("subset"):
            ds = load_dataset(spec["id"], spec["subset"], split=spec["split"], streaming=spec.get("limit") is not None)
        else:
            ds = load_dataset(spec["id"], split=spec["split"], streaming=spec.get("limit") is not None)
    except Exception as e:
        info["status"] = "load_failed"
        info["error"] = repr(e)[:300]
        return info

    limit = spec.get("limit")

    if spec["format"] == "parquet":
        # Materialize (limited if needed) -> parquet
        if limit:
            from datasets import Dataset
            rows = []
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                rows.append(row)
            mat = Dataset.from_list(rows)
        else:
            mat = ds  # already non-streaming
        mat.to_parquet(str(out_path))
    else:
        # jsonl fallback
        with out_path.open("w", encoding="utf-8") as f:
            i = 0
            for row in ds:
                if limit and i >= limit:
                    break
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                i += 1

    info["status"] = "ok"
    info["bytes"] = out_path.stat().st_size
    info["path"] = str(out_path)
    info["wall_seconds"] = round(time.time() - t0, 2)

    # sha256
    h = hashlib.sha256()
    with out_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    info["sha256"] = h.hexdigest()

    volume.commit()
    return info


@app.function(
    image=image,
    volumes={VOLUME_MOUNT: volume},
    timeout=300,
)
def write_manifest(results: list[dict]) -> dict:
    import datetime as dt
    import json
    from pathlib import Path

    manifest_path = Path(VOLUME_MOUNT) / "external" / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_v": 1,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "datasets": results,
        "decision_refs": ["slm-learning-105", "slm-learning-094"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    volume.commit()
    return {"manifest_path": str(manifest_path),
            "n_datasets": len(results)}


@app.function(
    image=image,
    volumes={VOLUME_MOUNT: volume},
    timeout=120,
)
def list_volume() -> dict:
    """Show what's currently in the slm-data volume."""
    import json
    from pathlib import Path

    base = Path(VOLUME_MOUNT)
    out = {}
    for p in sorted(base.rglob("*")):
        if p.is_file():
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            rel = str(p.relative_to(base))
            out[rel] = size
    return out


@app.local_entrypoint()
def main(only: str = "") -> None:
    """Pull every dataset (or a single one matching the `only` substring)."""
    import json as _json

    selected = DATASETS if not only else [
        d for d in DATASETS if only.lower() in d["id"].lower()
        or only.lower() in d["target"].lower()
    ]
    print(f"[main] pulling {len(selected)} dataset(s)")

    results = list(pull_one.map(selected))
    print()
    for r in results:
        status = r.get("status", "?")
        size_mb = r.get("bytes", 0) / (1024 * 1024) if r.get("bytes") else 0
        print(f"  {status:18}  {r.get('id','?'):45}  {size_mb:>8.1f} MB")

    manifest = write_manifest.remote(results)
    print(f"\nManifest: {manifest['manifest_path']}")
    print(_json.dumps(results, indent=2))
