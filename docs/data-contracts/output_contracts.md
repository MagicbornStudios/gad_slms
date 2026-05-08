# Output Contracts

**Status:** v1, locked 2026-05-08
**Decision:** `slm-learning-108`
**Companion:** `docs/data-contracts/coding_sft.md`,
`benchmarks/contracts.json`

Every dataset row AND every benchmark MUST declare an output
contract. Strict-contract training is blocked when sampled contract
match falls below threshold.

## Contract types

| Contract | Strictness | Description |
|---|---|---|
| `natural_language` | loose | Free-form English / Markdown answer |
| `gad_cli_command` | **strict** | Exact `gad <subcommand> ...` CLI string, runnable as-is |
| `tool_action_json` | **strict** | JSON `{"tool": "...", "args": {...}}` shape; rendered to CLI separately |
| `code_completion` | **strict** | Function body only, indented to fall under a given def |
| `function_definition` | **strict** | Complete `def name(...): ...` block |
| `full_script` | strict | Complete runnable program (competitive style allowed) |
| `patch_diff` | **strict** | Unified diff `--- a/... +++ b/... @@ ... @@` |
| `email_draft` | loose | Email body, optional subject |
| `classification_label` | **strict** | Exactly one label from a predefined set |

Strict contracts MUST be schema-validated before training. Loose
contracts use icontains / contains-any / human review.

## Per-row schema

Each training-data row carries a `target_contract` field:

```json
{
  "id": "ocr-fn-norm-12345",
  "source_corpus": "open-code-reasoning",
  "target_contract": "function_definition",
  "input": "...",
  "target": "def name(...):\n    ...",
  "language": "python",
  "schema_v": 1
}
```

For strict contracts the validator must verify the `target` parses
under the contract's grammar (e.g. `function_definition` → must
parse with `ast.parse`).

## Per-benchmark schema

Each benchmark declares which contracts it scores:

```json
{
  "benchmark": "gad_tools",
  "expected_contract": ["gad_cli_command", "tool_action_json"],
  "scoring": "assertion_or_schema"
}
```

Eval results MUST include:

```json
{
  "expected_contract": "...",
  "observed_contract_guess": "...",
  "contract_pass": true
}
```

`observed_contract_guess` is the validator's best guess at what the
model actually emitted (e.g. detected `natural_language` when
`gad_cli_command` was expected). `contract_pass` is `false` whenever
the observed contract is not in `expected_contract`.

## Validator

`scripts/data/validate_output_contract.py`:

- Samples N rows from a dataset (default 200, or full at <500 rows)
- Detects each row's declared contract
- Estimates match rate per contract
- Prints up to 5 examples of mismatches per contract
- Writes `reports/data_contracts/<dataset>_contract_report.json`
- **Blocks training** if strict-contract match < 95% (exit code 2)

CLI:

```sh
.venv/Scripts/python.exe scripts/data/validate_output_contract.py \
    --dataset data/processed/ocr-variants-2026-05-08/ocr_function_normalized/rows.jsonl \
    --strict-min 0.95
```

## Pre-train gate

Before any new SFT/LoRA run:

```text
1. Validator runs on the dataset.
2. If strict_contract_match < 0.95, training blocks (exit 2).
3. The validator's report is committed alongside the run manifest.
4. Reviewer can override with --force-train, but the override is
   logged in DECISIONS.xml as a per-run exception.
```

## Why this exists

The 2026-05-08 `tooluse-v2` finding: trained on telemetry pairs whose
`response` field included `Note: Build is broken on Windows.`-style
natural-language answers. Evaluated on `gad_tools` which expects
`gad note add ...`-style CLI commands. Result: 14/30 (46.7%).
Semantically correct, contract-wrong.

The contract gate would have caught this at dataset-prep time:
`tooluse-v2`'s training data is ~mixed natural_language +
tool_action targets, so strict contract match for `gad_cli_command`
would be far below 95% and the run would have been blocked until
the dataset was filtered or relabeled.

## Migration path for existing datasets

Existing JSONL datasets without `target_contract`:

1. Run `validate_output_contract.py --infer` to attach a guessed
   contract per row.
2. Filter by inferred contract or relabel.
3. Save filtered dataset with `_v2_contract.jsonl` suffix.
4. Resume training with the filtered dataset.

The OCR variants in `data/processed/ocr-variants-2026-05-08/`
already declare `target_format` (per `coding_sft.md`); the
validator treats `target_format` and `target_contract` as the same
field for backwards compatibility.
