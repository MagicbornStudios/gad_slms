# Training salvage strategy

**Date:** 2026-05-08
**Decision refs:** `slm-learning-094`, `slm-learning-096`,
`slm-learning-103`, `slm-learning-107`, `slm-learning-109`,
`slm-learning-110`, `slm-learning-111`, `slm-learning-112`

## Principle

> Failed training is not wasted if it produces:
> a failure taxonomy, a corrected contract, a negative preference
> pair, a salvage decision, or a better gate.

Don't keep training a bad model out of hope. Salvage requires a
classified next-action with a measurable success bar.

## Five salvage modes

### 1. Continue-from-bad-checkpoint

Use when:
- Loss curve was clean and the bad eval is style/format, not knowledge
- Corrected dataset is small; you want the model's existing
  representation as a warm start
- A 2-arm A/B vs fresh-base would let you measure the benefit

Procedure:
1. Mark checkpoint `salvage_candidate`
2. Build the corrected dataset with contract validation passed
3. Run BOTH:
   - **Arm A:** fresh-base + corrected dataset
   - **Arm B:** continue-from-checkpoint + corrected dataset
4. Eval both at same N on same benchmarks
5. Keep whichever wins; archive the other

Decision rule: `B > A` justifies continuing. Otherwise restart.

### 2. Restart-from-base

Use when:
- The bad checkpoint's output style is so divergent that continuing
  would inherit the divergence
- Corrected dataset is large enough to teach the right shape from
  scratch

Default for: format-mismatch failures where continue would
re-pollute the new training (e.g. tooluse-v2's natural-language
outputs would fight against `gad_cli_command` targets).

Procedure:
1. Mark old checkpoint `negative_teacher` (mine for preference pairs)
2. Train fresh corrective from base on the corrected dataset
3. Optionally DPO-tune the corrective using the old checkpoint's
   outputs as `rejected`

### 3. Negative-teacher (DPO/KTO/SimPO source)

Use when:
- The bad checkpoint produces systematically wrong outputs
- Those outputs are useful as `rejected` examples paired with the
  correct `chosen`

Procedure:
1. Mark checkpoint `negative_teacher`
2. Mine `(prompt, chosen, rejected)` triples (see
   `scripts/data/mine_tooluse_preference_pairs.py`)
3. Use triples for preference tuning of the corrective model
4. Once mined dry, the negative_teacher can be archived or rejected

Cost-effective: every contract failure becomes preference data
without extra inference cost.

### 4. Skeleton-adapter (archive)

Use when:
- The bad checkpoint has interesting lineage / lessons but no
  current training role
- Future runs may want to compare against it as a known-bad
  reference

Procedure:
1. Mark checkpoint `skeleton_adapter`
2. Keep the MANIFEST.json + lineage; weights can be cold-archived
3. Reference in future research reports as the "we used to do X"
   anchor

Storage: Modal volume cold path or HF Hub `private` repo.

### 5. Quarantine + delete

Use when:
- The checkpoint is unsafe, corrupt, or licensed against use
- Continuing-from would replicate the harm

Procedure:
1. Mark `quarantined` immediately
2. Move to a sweep-deletion queue
3. Delete in next ops sweep (not retained in registry)

## Decision flowchart

```
                  bad eval result
                        │
              ┌─────────┴─────────┐
              │                   │
   was loss curve clean?   was output contract wrong?
              │                   │
        ┌─────┴─────┐         ┌───┴───┐
        Y           N         Y       N
        │           │         │       │
  knowledge?  rejected   salvage_     genuine
        │     (delete)   candidate    algorithm fail
        │                    │       (mark rejected;
   2-arm A/B           continue?     consider arch
   continue vs           A/B test    experiments)
   fresh-base               │
        │              negative_teacher
        ▼              + fresh corrective
   keep winner               +
                       DPO with mined pairs
```

## When NOT to salvage

- Loss curve was unstable (NaN, oscillation, divergence) — these
  are training-process failures, not checkpoint-quality failures
- The eval gap is so large (e.g. <50% of canonical) that no
  continue-from would close it cheaply
- The architecture or hyperparams were wrong — better to fix
  upstream and retry, not salvage

## The 2-arm A/B template

For continue-from decisions:

```text
Arm A — Fresh corrective:
  base: <base model>
  dataset: <corrected dataset>
  recipe: <standard hyperparams>
  cost: <estimate>

Arm B — Continue from bad:
  starting point: <bad checkpoint>
  dataset: <corrected dataset>  (SAME as A)
  recipe: <standard hyperparams>  (SAME as A)
  cost: <estimate>

Eval — both arms:
  benchmarks: <same set>
  N: <same N per benchmark>
  seed: <same seed>

Decision rule:
  B > A by >2pp on the gate benchmark → keep B
  B ≤ A → restart from base, archive checkpoint as
          negative_teacher or skeleton_adapter
```

## Active salvage cases

### tooluse-sanity-v2-modal-l4-2026-05-08

- **Status:** salvage_candidate (per slm-learning-109)
- **Why:** failed gad_tools 14/30; outputs natural language instead
  of gad CLI commands. Loss curve was clean (0.406, matches v1). The
  model learned tool-use INTENT but not tool-use FORMAT.
- **Salvage plan:**
  - Mine preference pairs: ✓ done — 8 pairs in
    `data/preference/tooluse_contract_failures_dpo.jsonl`
  - Build corrected dataset with `target_contract: gad_cli_command`
    or `tool_action_json`. Filter telemetry pairs to keep only
    rows whose `command` field is a real gad CLI invocation.
    Discard natural-language rows.
  - 2-arm A/B:
    - **Arm A** — fresh base + corrected dataset
    - **Arm B** — continue from tooluse-v2 + corrected dataset
    - **Arm C** — small converter model
      (`natural_language_tool_intent → gad_cli_command`) used as
      a post-processing step
  - Decision rule: best of A/B/C on `gad_tools` n=30 +
    `gad_tools_hard` n=100 (when scaffolded)

### ladder-7b-coder-2026-05-08 (raw OCR)

- **Status:** rejected (per slm-learning-110)
- **Future use:** may become `negative_teacher` for the corrected
  OCR LoRA's DPO pass. The model's competitive-programming style
  outputs paired with HE-style `chosen` would teach the corrective
  model to prefer function-completion shape.

### ladder-1p5b-ocr-no-think-2026-05-08

- **Status:** rejected (per slm-learning-110)
- **Why:** strip-only-think regressed both HE (-9.2pp) and MBPP
  (-2.5pp). Format-strip is the dominant lever, not think-strip.
- **Skeleton-adapter retain:** YES — useful as anchor for "shape >
  length" lesson. MANIFEST.json kept; weights cold-archived.

### ladder-1p5b-ocr-fn-norm-2026-05-08

- **Status:** staging (pending 7B confirmation)
- **Why:** lifted both HE (+6.7pp) and MBPP (+3.0pp) over 1.5B base.
  Becomes `canonical` if 7B + fn_norm also lifts.

## See also

- `docs/checkpoints/checkpoint_status_policy.md`
- `reports/diagnostics/ocr_variant_breakthrough_2026-05-08.md`
- `data/preference/tooluse_contract_failures_dpo.jsonl`
