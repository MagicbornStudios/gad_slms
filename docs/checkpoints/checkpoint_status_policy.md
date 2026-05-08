# Checkpoint status policy

**Status:** v1, locked 2026-05-08
**Decision:** `slm-learning-109`
**Companion:** `reports/research/training_salvage_strategy.md`

Every checkpoint / adapter in the model registry MUST carry a
`status` field. Failed training is not waste; it has a status.

## Statuses

| Status | Meaning | Action allowed |
|---|---|---|
| `candidate` | Just trained; pre-eval | wait for evals to populate |
| `staging` | Beat its target on private eval; pre-promotion | promote to canonical |
| `canonical` | Promoted; serves as fallback baseline | archive when superseded |
| `rejected` | Failed eval; permanently dropped | delete (or keep as cold archive) |
| `salvage_candidate` | Failed final-output contract but learned task knowledge | continue-from / DPO source / converter source |
| `negative_teacher` | Useful mainly as `rejected` outputs for DPO/KTO/SimPO | mine for preference pairs |
| `skeleton_adapter` | Archived failed adapter with useful lineage / lessons | reference only; do not load |
| `quarantined` | Unsafe / corrupt / unusable | DO NOT continue; delete in next sweep |

## Status transitions

```
candidate ──> staging ──> canonical
   │            │            │
   │            ▼            ▼
   ▼         rejected    archived
salvage_candidate ──> rejected
   │
   ▼
negative_teacher ──> mined ──> rejected
```

## Decision rules

### When to mark `salvage_candidate`

A checkpoint becomes `salvage_candidate` if ALL three:

1. Failed its primary eval gate (e.g. <0.85 of canonical's score)
2. Has reasoning / task knowledge worth preserving (loss curve was
   clean; the model "learned something" even if outputs are
   contract-wrong)
3. Could be either: continued-from with a corrected dataset, OR mined
   for negative-preference pairs

Example: `tooluse-sanity-v2-modal-l4-2026-05-08` — failed gad_tools
14/30 because output contract is wrong (natural language instead of
gad CLI), but the model clearly understands the tool-use intent.
Mark `salvage_candidate`.

### When to mark `negative_teacher`

A checkpoint is `negative_teacher` if:

1. The model's outputs are systematically wrong-contract / wrong-
   format
2. Those wrong outputs are STILL useful as `rejected` examples in
   preference learning (DPO/KTO/SimPO)
3. Continuing-from is unlikely to recover the model

The use case is: train `corrected-model-vN` on `chosen` outputs,
then DPO it against the negative_teacher's `rejected` outputs. The
negative_teacher need never be served — it's a data source.

### When to restart from base

If a candidate checkpoint scores below base on the eval AND a
fresh-base run with the corrected dataset SHOULD plausibly beat it:

1. Mark the candidate `salvage_candidate` (with note: continue=NO).
2. Train a fresh corrective LoRA from base on the corrected dataset.
3. Compare fresh vs continued in a 2-arm A/B at the same N.
4. Keep whichever wins.

The 2-arm A/B is mandatory before declaring "continue from bad
checkpoint helped."

### When to quarantine

Mark `quarantined` if:

- The checkpoint contains data exfiltration / unredacted secrets
- The checkpoint produced unsafe outputs that could be replicated
- The training data was discovered to be license-incompatible
- The adapter file is corrupt / fails to load

Quarantined checkpoints are deleted on the next sweep, not stored
as archives.

## Per-checkpoint metadata

Each entry in the registry MUST carry:

```json
{
  "delta_id": "tooluse-sanity-v2-modal-l4-2026-05-08",
  "status": "salvage_candidate",
  "status_reason": "Failed gad_tools 14/30 — natural-language outputs instead of gad CLI commands. Reasoning + tool-call context preserved. Continue=NO; mine for negative pairs (8 captured); train fresh corrective with contract-validated dataset.",
  "status_set_at": "2026-05-08T22:30:00Z",
  "status_set_by": "dr-stein",
  "salvage_uses": [
    {"kind": "preference_pairs", "path": "data/preference/tooluse_contract_failures_dpo.jsonl", "n_pairs": 8}
  ],
  "decision_refs": ["slm-learning-109", "slm-learning-111"]
}
```

Stored as a sibling to the adapter MANIFEST.json or in a central
registry (location TBD per monorepo decision).

## Examples

### Candidate that became canonical
`ladder-7b-coder-2026-05-08` (raw OCR LoRA): currently `rejected`
post-diagnosis. May become `negative_teacher` for the
corrected-OCR LoRA's DPO pass.

### Salvage candidate
`tooluse-sanity-v2-modal-l4-2026-05-08`: current `salvage_candidate`.
Continue=NO (correction needed, not extension). Mine=YES (8 pairs
already captured).

### Quarantine (hypothetical)
A checkpoint trained on un-redacted telemetry would be
`quarantined`.

## See also

- `reports/research/training_salvage_strategy.md` — when/how to
  salvage in detail
- `slm-learning-096` — every training run produces 3 reusable
  artifacts (weights + outputs corpus + regression journal); status
  policy ensures the artifacts get classified, not just trained
- `slm-learning-100` — Delta Graph schema
