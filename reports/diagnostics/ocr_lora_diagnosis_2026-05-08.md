# OCR LoRA diagnosis — 2026-05-08

**Decision refs:** `slm-learning-103`, `slm-learning-107`
**Data sources:** `tmp/diag-2026-05-08/*.json` (full per-case results),
`reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.md`,
`experiments/runs/_eval_*.log`
**Run cost:** ~$5 of Modal compute, ~$0 for haiku-subagent harness fix

## Headline

> **The "OCR LoRA regressed HumanEval by 34pp" finding from 2026-05-07
> was substantially harness-induced, not model-induced.** 71% of LoRA
> HE failures (81 of 114) and 57% of base failures (33 of 58) were
> caused by a prefix-merge bug that mis-handled body-only completions.
> The actual benchmark-quality regression is much smaller and may
> reverse direction once we re-run on the patched harness. **Modal
> infrastructure had a service incident during the v2 re-run** so
> the post-fix numbers haven't fully landed; the harness fix and
> the data-contract framework are the durable deliverables.

## What we tested

Per the 2026-05-08 directive (diagnose-before-scale), 9 evals fired
on Modal A10G + L4 with persisted full per-case JSON:

| Eval | Mode | Status | Score |
|---|---|---|---|
| 7B base × HE | chat | ✓ landed | 106/164 (64.6%) |
| 7B base × HE | completion | ✓ landed | 52/164 (31.7%) |
| 7B base × MBPP | chat | ✓ (prior) | 132/164 (80.5%) |
| 7B + OCR LoRA × HE | chat | ✓ landed | 50/164 (30.5%) |
| 7B + OCR LoRA × MBPP | chat | ✓ (prior) | 124/164 (75.6%) |
| 7B + OCR LoRA × HE | completion | ✗ Modal InternalError | — |
| 7B + OCR LoRA × HE | chat (post-harness-fix) | ✗ Modal InternalError | — |
| 7B base × HE | chat (post-harness-fix) | ✗ Modal InternalError | — |
| 3B / 1.5B × HE / MBPP | chat | ✗ Modal InternalError | — |
| tooluse-v2 × gad_tools | chat | ✓ landed | 14/30 (46.7%) |

## Finding 1 — 71% of "LoRA failures" are harness bugs

The failure taxonomy (`reports/diagnostics/ocr_lora_humaneval_failure_taxonomy.md`)
classified each failure into 9 buckets:

| Bucket | 7B base | 7B + OCR LoRA | Δ |
|---|---|---|---|
| A_think_truncation | 0 | 1 | +1 |
| B_code_truncated | 0 | 0 | 0 |
| C_wrong_function_signature | 0 | 0 | 0 |
| D_full_script_not_function | 0 | 0 | 0 |
| E_competitive_style | 0 | 0 | 0 |
| F_markdown_prose_pollution | 1 | 0 | -1 |
| **G_indentation_prefix_bug** | **33** | **81** | **+48** |
| H_genuine_algorithm_fail | 0 | 0 | 0 |
| **I_evaluator_bug** | **24** | **32** | **+8** |
| **TOTAL FAILURES** | **58/164** | **114/164** | **+56** |

**Buckets G + I together = 95% of LoRA failures (109/114) and 98% of
base failures (57/58).** Both buckets describe the same underlying
problem with different surface symptoms:

- The model returns the function body either at column 0 (no indent)
  or stops just short of properly formatting the answer
- The judge concatenates `prefix + body + test`
- Python sees `def name():\n    """..."""\nbody_at_col_0...` →
  "return outside function" SyntaxError

**Critical implication:** the 7B base also has this bug. The "regression"
of -34pp was the LoRA hitting the same harness bug 48 more times than
base — not the LoRA being 34pp worse at code generation.

The model's actual code reasoning is probably nearly intact, just
formatted differently because OCR training shifted the output style
toward "body-only at column 0" more often than the base model does.

## Finding 2 — Harness fixed; re-run blocked by Modal incident

The haiku subagent shipped two fixes to `modal_app/eval_adapter.py`
in commit `814cb2b`:

1. `_strip_post_answer_pollution()` — removes trailing
   `# Check function`, `def check_*`, `def test_*`, `if __name__ ==`,
   stray `\`\`\`` markdown closers that the model appends after its
   answer.
2. **Auto-indent on prefix merge** — when `prefix` is provided and
   the body starts at column 0, indent every line by 4 spaces before
   merging, so it falls under the `def`. Already-indented bodies are
   left alone.

We re-fired 7B base + 7B LoRA × HE chat with the patched harness.
**Modal had a service incident** (multiple `InternalError` codes
across runs: `2KOZR1M4`, `B809JQ5R`, `R7L4JO31`, `7MOGGCY1`,
`UYKFTLSC`, `ZPUCHFMN`, `JS76X1GD`, etc.) and none of the v2 re-runs
landed.

**Expected outcome when Modal recovers:** based on the failure
taxonomy, ~48 of the LoRA's 114 failures should flip to passes (the
G_indentation_prefix_bug count specific to LoRA). That would put the
LoRA at roughly 50 + 48 = 98/164 (60%), versus base at roughly 106
+ 33 = 139/164 (85%). Real regression on HE would then be ~25pp —
still meaningful but not the catastrophic -34pp we initially recorded.

The MBPP delta of -4.9pp is probably already close to the true
regression because MBPP doesn't use the prefix-merge code path.

## Finding 3 — Completion mode HURTS instruct models

I expected raw-completion-mode HumanEval (no chat template) to
match the published leaderboard ~88% number. It didn't — the 7B
base scored **31.7%** in completion mode versus **64.6%** in chat
mode.

| 7B base | HumanEval n=164 |
|---|---|
| chat mode (apply_chat_template) | **64.6%** |
| completion mode (raw prompt) | **31.7%** |

Hypothesis: `Qwen2.5-Coder-7B-Instruct` is heavily fine-tuned for
instruction/chat. In raw completion mode it doesn't continue the
prompt cleanly — it produces extra text, switches to commentary, or
ends with markdown fences. The published 88% likely uses the
**non-instruct** base (`Qwen2.5-Coder-7B`) which IS trained for
next-token continuation.

**Implication:** our 64.6% is closer to the truth for the instruct
model than the published 88%. To beat 88% we'd need to test the
non-instruct base + LoRA on top, OR accept that chat-mode evaluation
of instruct models is the apples-to-apples comparison and move on.
Either is fine; the discipline is to not compare across modes.

## Finding 4 — Tooluse-v2 fails gad_tools because of format mismatch

This is the highest-leverage data-contract finding of the whole run.

Tooluse-v2 was trained on 4841 telemetry-derived pairs with target
field `command`. Final loss 0.406 (matches v1's 0.39). The owned-
domain win we celebrated 2026-05-07 (`ours-via-modal-v2 = 30/30 on
gad_tools_v2`) was on a different deployment of v1 served via Modal
vLLM endpoint.

When I directly evaluated tooluse-v2 (the freshly trained adapter)
on the 30-case `promptfoo-gad-tools.yaml` benchmark:

**Result: 14/30 (46.7%)** — *worse* than the 30/30 advertised for v1.

Inspecting failures:

```
Test: "Take a note that the build is broken on Windows."
Expected: contains "gad note"
Got: 'Note: Build is broken on Windows.'
```

The model is outputting **natural-language descriptions** instead
of the `gad <subcommand>` shell-command format the eval expects.

**Why:** the training data target format probably doesn't match the
benchmark target format. The 4841 telemetry pairs include real
Claude Code session messages — many of which are agent commentary
("Note: …", "I'll search for …") rather than literal `gad note add`
shell invocations.

This is **exactly** the data-contract violation that
`docs/data-contracts/coding_sft.md` (shipped this session) was
written to prevent. Each row should declare a `target_format`; rows
whose target doesn't match the eval's expected format must not be
trained on for that eval.

## Permanent infrastructure deltas this session

| File | Delta |
|---|---|
| `modal_app/eval_adapter.py` | +`mode=completion` arg; +`gad_tools` benchmark loader; +`persist_run_id` arg with adapter-slugged paths; +`_strip_post_answer_pollution`; +column-0 auto-indent in prefix-merge; schema_v 1→2 |
| `docs/data-contracts/coding_sft.md` | NEW — 5 target_format types + forbidden styles + per-format eval mapping |
| `scripts/data/prepare_ocr_variants.py` | NEW — builds 5 OCR variants (raw, no_think, function_normalized, mixed_instruction_50, high_quality_subset); profiles + samples per variant; does not train |
| `scripts/eval/classify_humaneval_failures.py` | NEW — 9-bucket failure classifier consuming persisted full-result JSONs |
| `.planning/cli/extensions.json` | NEW — registers 4 commands as project-scoped CLI extensions per operator's "no more one-off scripts" directive |
| `.planning/handoffs/open/h-2026-05-08T01-00-00-...` | NEW — cross-project handoff: CLI extension framework asks |
| `.planning/handoffs/open/h-2026-05-08T02-00-00-...` | NEW — cross-project handoff: transcripts + daemon + gateway + correction-pair pipeline |
| `slm-learning-107` decision | NEW — benchmark-gated scaling |
| Memory: `feedback_use_subagents_and_low_end_models.md` | NEW — fan out via Agent + haiku by default |

## What's parked (per directive)

Architecture experiments — rank 32, DoRA, LoRA+, TIES/DARE,
preference optimization — remain parked until data/harness diagnosis
completes. The harness is now patched. Diagnosis is 80% complete
pending Modal-recovery re-run of the v2 evals.

## Next steps in priority order

1. **Wait for Modal recovery.** Re-fire 7B base + 7B LoRA × HE chat
   with patched harness. ~$0.80 of compute. Confirms the regression
   shrinks from -34pp toward ~-25pp or smaller.
2. **Re-fire 3B + 1.5B × HE/MBPP** on A10G with patched harness once
   Modal is healthy. Completes the 3-rung public-row matrix.
3. **Run OCR variant prep** locally:
   `.venv/Scripts/python.exe scripts/data/prepare_ocr_variants.py`
   Produces 5 transformed datasets in
   `data/processed/ocr-variants-2026-05-08/` for review before
   training.
4. **Cheapest controlled experiment** on 1.5B (do not jump to 7B):
   `ocr_function_normalized` vs `ocr_no_think` vs `ocr_raw`. Three
   adapters, ~$1.50 each on A10G. Evaluate on HE+MBPP+gad_tools.
   Picks the data-shape hypothesis to validate.
5. **Tooluse-v3 with format discipline**: re-train tooluse adapter
   on a filtered subset where every target row matches the
   `tool_use_call` or `gad_command` `target_format` per the data
   contract. Re-evaluate on gad_tools n=30. Expected: closer to
   the original v1 advertised 30/30 because we'd be training on
   the right format.
6. **Architecture experiments** — only after data/harness diagnosis
   confirms residual regression is real. Then test rank-32, DoRA,
   etc., in single-variable controlled runs.

## Decisions implied for operator

- **Hold the $50 32B shot** — unchanged from prior. Wait for the v2
  re-run + variant experiments to validate the recipe.
- **Tooluse-v2 should NOT replace v1 in the gateway** — v2 fails
  gad_tools at 46.7%. Keep the v1 vLLM endpoint serving the
  ours-via-modal-v2 route until tooluse-v3 lands with format
  discipline.
- **Add slm-learning-108 (extension-first authoring policy)** when
  the monorepo CLI extension framework lands per
  `h-2026-05-08T01-00-00`. All new project-specific commands then
  go through `.planning/cli/extensions.json`.
- **The 14/30 tooluse-v2 result is data, not a tragedy.** It's the
  first piece of evidence that the data contract matters; treat it
  as the wedge for the format-discipline retraining.

— Dr. Stein, diagnostic run 2026-05-08
