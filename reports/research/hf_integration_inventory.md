# HuggingFace Integration Inventory

**Date:** 2026-05-09
**Author:** claude-code / Gilgamesh session

---

## 1. Bottom line

`gad hf` is the canonical HuggingFace surface for the entire monorepo. It covers both consumption (searching and downloading models and datasets from the Hub) and contribution (publishing our owned DPO preference data as community datasets). The CLI namespace lives in `vendor/get-anything-done/bin/commands/hf.cjs` — the same Node.js/CommonJS layer as every other `gad` command — and delegates to `huggingface-cli` for write operations. The Python library (`huggingface_hub`) remains in `slm_learning`'s domain; `gad hf` stays dependency-free by shelling out or calling the public REST API directly via `fetch`.

---

## 2. Current state

HuggingFace integration in `slm_learning` is already substantial but **entirely Python-side and Modal-centric**:

- `requirements.txt` pins `transformers>=4.40.0` — the HF Transformers core.
- `modal_app/pull_datasets.py` calls `pip_install("huggingface_hub>=0.30", "datasets>=3.0")` inside Modal image definitions and pulls six datasets (the-stack-smol-xs, hh-rlhf, oasst2, SWE-bench) into a remote volume. No local disk touched per slm-learning-105 (hardware policy).
- `scripts/download_datasets.py` uses `datasets.load_dataset(...)` to pull seven evaluation corpora (humaneval, mbpp, gsm8k, arc, hellaswag, oasst1) into `data/external/` as Parquet files with preview JSON.
- `modal_app/serve_vllm.py` loads base models via `DEFAULT_BASE = "Qwen/Qwen2.5-1.5B-Instruct"` — implicitly resolving from HF Hub at container build time.
- **No `HF_TOKEN` is referenced anywhere in slm_learning source** (only in venv site-packages). Public models are accessed unauthenticated. Gated models (NousCoder-14B, Hermes-4-14B) would require token injection at Modal secret level — not yet wired.
- The `gad` CLI had **zero HuggingFace surface** before this session. The `nous.cjs` command (GitHub search for Nous Research) was the closest adjacent command.

---

## 3. The CLI surface

| Subcommand | Use case | Auth required |
|---|---|---|
| `gad hf models search <query>` | Discover models by keyword; filter by pipeline tag | No (public) |
| `gad hf models show <model-id>` | Inspect model card: downloads, license, tags, file count | No (public) |
| `gad hf datasets search <query>` | Discover datasets: DPO, preference, reasoning corpora | No (public) |
| `gad hf datasets show <dataset-id>` | Inspect dataset card metadata | No (public) |
| `gad hf download <id> --target <path>` | Fetch model or dataset weights locally | Optional (gated models need `HF_TOKEN`) |
| `gad hf push-dataset <path> --repo-id <id>` | Publish owned DPO data to HF Hub | Yes (`HF_TOKEN`) |
| `gad hf whoami` | Verify token + show org memberships | Yes (`HF_TOKEN`) |

All subcommands accept `--json` for machine-readable output. Settings are stored under the `hf.*` namespace in `gad-config.toml`:

| Key | Default | Scope |
|---|---|---|
| `hf.api_endpoint` | `https://huggingface.co` | user |
| `hf.token_env_var` | `HF_TOKEN` | user |
| `hf.default_download_dir` | `~/.gad/hf-cache` | user |
| `hf.dataset_publish_default_visibility` | `private` | user |

---

## 4. Adoption flows

### (a) Pull NousCoder-14B for 14B baseline eval

```sh
# Set token first (gated model)
export HF_TOKEN=hf_...

gad hf download NousResearch/NousCoder-14B \
  --target slm_learning/models/nouscoder-14b \
  --type model

# Then point serve_vllm.py at the local volume path
# DEFAULT_BASE = "/models/nouscoder-14b"
```

This stages weights in `slm_learning/models/nouscoder-14b/` for Modal volume upload or direct eval. The `--target` flag overrides `hf.default_download_dir` per invocation.

### (b) Inspect Hermes-4-14B before serving

```sh
gad hf models show NousResearch/Hermes-4-14B --json
```

Returns `{ id, downloads, likes, license, tags, pipeline_tag, siblings, lastModified }`. Use before committing to a Modal deploy to verify license compatibility, quantization notes, and file count (siblings field = number of shards).

### (c) Publish seed DPO rows

```sh
# Stage the seed file
cp .planning/datasets/preference-pairs/tool_use_pairs_seed.jsonl \
   /tmp/gad-publish/tool_use_pairs_2026-05-09-seed.jsonl

# Upload as private initially
gad hf push-dataset /tmp/gad-publish/tool_use_pairs_2026-05-09-seed.jsonl \
  --repo-id magicbornstudios/gad-tool-use-preference \
  --private \
  --message "seed batch 2026-05-09 — 47 tool_use preference pairs"
```

The `--private` flag is the default (see `hf.dataset_publish_default_visibility`). Publishing from `.planning/datasets/` as public requires `--i-confirm-public` to prevent accidental operator-private leaks.

---

## 5. Connection to soul-routes

`slm_learning/src/soul_routes/` maps soul IDs to inference adapter targets. When a soul's `adapter_targets` entry references a HuggingFace model ID (e.g. `NousResearch/Hermes-4-14B`), the weight-fetch path is:

```
gad hf download <model-id> --target slm_learning/models/<slug>
  → weights land locally or on Modal volume
  → modal_app/serve_vllm.py loads from volume path
  → OpenAI-compatible endpoint exposed at stable Modal URL
  → soul_route.adapter_targets entry updated to point at Modal URL
```

The `gad hf download` command is the canonical weight-fetch entry point for this pipeline. It replaces ad-hoc `huggingface-cli download` calls scattered across run scripts, adds settings-aware defaults, and leaves an audit trail via the `gad` log layer (`.planning/.gad-log/`).

---

## 6. Open questions

**When to make tool-use-preference public.** The seed dataset is generated from `gad` planning interactions. Any rows sourced from operator-private planning data (decision bodies, handoff content, project-internal task goals) must be scrubbed before public release. A consent + scrub pass is needed before flipping `hf.dataset_publish_default_visibility` to `public`. Suggested gate: a `gad datasets scrub-check --projectid global` command (not yet built) that flags planning-sourced rows.

**HF Pro features.** Inference Endpoints (HF's serverless GPU serving) could complement Modal for burst inference. Cost comparison needed: HF Inference Endpoint L4 vs Modal L4 at our usage pattern. HF Spaces (Gradio/Streamlit demos) are relevant if we ever publish a public eval leaderboard. Neither requires immediate action.

**Org-level ownership.** Dataset and model repos should live under the `magicbornstudios` HF org (not personal accounts) so ownership survives individual account changes. Org creation + team seat assignment is a one-time manual step before first public push.

**gated-model token injection into Modal.** NousCoder-14B and Hermes-4-14B are gated. `gad hf download` handles local download with `HF_TOKEN` in env. For Modal volume pre-population (`modal_app/pull_datasets.py`), the token needs to land in a Modal secret (`HF_TOKEN`) and be injected at image build via `.secret(modal.Secret.from_name("hf-token"))`. That wiring is not yet in `serve_vllm.py` — currently only public Qwen models are loaded.
