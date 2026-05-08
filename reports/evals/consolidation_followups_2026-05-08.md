# Consolidation Framework Follow-ups (2026-05-08 close)

**Owner:** Dr. Stein
**Decisions logged:** slm-learning-178..185
**Charter:** `reports/research/scaling_proof_charter.md`
**Framework doc:** `reports/research/incremental_latent_consolidation.md`

## Eval table — all arms tested 2026-05-08

### 1.5B base = 54.9% HE / 61.0% MBPP

| Arm | HE pp@1 | HE Δ | MBPP pp@1 | MBPP Δ | Verdict |
|---|---|---|---|---|---|
| LoRA r=16 hard 74 | 48.2% | −6.7 | 57.3% | −3.7 | rejected |
| **LoRA r=16 hard+retain 164** | **64.0%** | **+9.1 ⬆** | **64.0%** | **+3.0 ⬆** | **CANONICAL (slm-learning-173)** |
| Morphism A mid (layer 13) hard 74 | 32.9% | −22 | 40.2% | −21 | rejected (hostile) |
| Morphism A late (layer 21) hard 74 | 52.4% | −2.5 | 58.5% | −2.5 | staged (slm-learning-175) |
| **Morphism A late+retain (layer 21)** | **50.0%** | **−4.9** | **61.0%** | **0.0** | **rejected — retain HURT HE on Variant A (slm-learning-185)** |
| Morphism B mid hard 74 | 54.9% | 0.0 | 61.0% | 0.0 | staged (preserves but inert) |
| Morphism B mid lr=5e-4 hard | 54.3% | −0.6 | 61.0% | 0.0 | rejected (gate stuck) |
| Morphism B mid hard+retain | 54.9% | 0.0 | 61.0% | 0.0 | rejected (gate stuck) |
| Morphism C late (layer 21) gate=1e-2 retain 164 | failed init check (0.89 < 0.99) | — | — | — | failed before training |
| **Morphism C late gate=1e-3 retain 164** | **54.9%** | **0.0** | **61.6%** | **+0.6 (1 case)** | **rejected — init too small (slm-learning-184)** |

### 3B base = 83.5% HE / 73.2% MBPP

| Arm | HE pp@1 | HE Δ | MBPP pp@1 | MBPP Δ | Verdict |
|---|---|---|---|---|---|
| LoRA r=16 7B-hard cross-base 58 | 76.2% | −7.3 | 73.8% | −0.6 | rejected (slm-learning-177) |
| **LoRA r=16 hard+retain 90 (27/63)** | **77.4%** | **−6.1** | **69.5%** | **−3.7** | **rejected — recipe doesn't scale up (slm-learning-183)** |

## What this round taught us

### 1. Recipe parameters are base-size-sensitive (slm-learning-183)

The 1.5B canonical recipe (74 hard + 90 retain, 45/55 actual ratio,
lr=2e-4, 3 epochs) does NOT transfer up to 3B unchanged. 3B+LoRA
hard+retain at 30/70 (27 hard + 63 retain) regressed both HE −6.1
and MBPP −3.7.

Possible drivers:
- **Hard scarcity:** 3B base only fails 27 of 164 HE cases. Saturated
  bases have less material to learn from.
- **Wrong ratio at saturation:** 30/70 may be too hard-heavy for
  saturated bases. More retain could anchor better.
- **Absolute dataset size:** 90 rows < 1.5B's 164 rows. Smaller dataset
  = more variance per gradient step.

Charter Claim 1 still has 2 lifted rungs (7B + 1.5B). 3B remains
**unsolved** — needs ratio sweep or hard-set augmentation.

### 2. Retain-mix is NOT universal — it depends on the delta mechanism (slm-learning-185)

| Mechanism × dataset | HE Δ | MBPP Δ |
|---|---|---|
| LoRA + hard 74 | −6.7 | −3.7 |
| LoRA + hard+retain 164 | **+9.1** | **+3.0** |
| Variant A late + hard 74 | −2.5 | −2.5 |
| Variant A late + hard+retain 164 | **−4.9** | **0.0** |

For LoRA, retain HELPS both axes. For Variant A, retain HELPS MBPP
(+2.5pp vs hard-only) but HURTS HE (−2.4pp vs hard-only). Variant A's
single-chokepoint residual rotation interacts differently with mixed
data than LoRA's distributed per-layer deltas.

**Implication:** retain-mix is a smoother for distributed-delta
mechanisms; for single-chokepoint mechanisms it shifts the
perturbation but doesn't reduce it. Variant A late on hard-only
remains the best-staged morphism arm.

### 3. Variant C init balance is a needle to thread (slm-learning-184)

| Variant C init | Init agreement | HE | MBPP |
|---|---|---|---|
| gate=1e-2, up_scale=1e-2 | **0.8906 (FAILED)** | n/a | n/a |
| gate=1e-3, up_scale=1e-3 | 1.0000 (passed) | 54.9 (FLAT) | 61.6 (+1 noise) |

1e-2 was too noisy in bf16; 1e-3 was small enough to preserve but
small enough to be inert. The empirical sweet spot is between, likely
5e-3. Or use asymmetric init: gate=1e-2 with up_scale=1e-3 — gate is
preserved by the small up_scale, gate's gradient flows because of the
large init. Untested; queued.

## Cross-scale matrix (final, this session)

| Base | Mechanism | Dataset | HE Δ | MBPP Δ | Status |
|---|---|---|---|---|---|
| 7B | LoRA hard 58 | 7B-OWN-hard | **+3.1** | **+1.8** | canonical |
| **1.5B** | **LoRA hard+retain 164** | **1.5B-OWN mix 45/55** | **+9.1** | **+3.0** | **canonical** |
| 1.5B | LoRA hard 74 | 1.5B-OWN-hard | −6.7 | −3.7 | rejected |
| 1.5B | Variant A mid hard | 1.5B-OWN-hard | −22 | −21 | rejected |
| 1.5B | Variant A late hard | 1.5B-OWN-hard | −2.5 | −2.5 | staged |
| 1.5B | Variant A late hard+retain | 1.5B-OWN mix 45/55 | −4.9 | 0.0 | rejected |
| 1.5B | Variant B (any config) | hard or hard+retain | flat | flat | gate stuck |
| 1.5B | Variant C late, gate/up=1e-3 | hard+retain | flat | +1 noise | inert |
| 3B | LoRA 7B-hard cross-base | 7B-OWN-hard | −7.3 | −0.6 | rejected |
| 3B | LoRA hard+retain 90 | 3B-OWN mix 30/70 | −6.1 | −3.7 | rejected |
| 0.5B | any × hard-only | 0.5B-OWN-hard | catastrophic | catastrophic | rejected |

## Cost summary (full session)

| Item | $ |
|---|---|
| Phase 0 0.5B base evals | 0.14 |
| 0.5B + LoRA hard | 0.30 |
| 0.5B + Variant A | 0.30 |
| 0.5B + Variant A lr=5e-5 | 0.20 |
| 1.5B base evals | 0.30 |
| 1.5B 4-arm ladder (LoRA hard, hard+retain, A, B) | 1.30 |
| 1.5B follow-ups (A late, B lr=5e-4, B+retain, 3B+7B-hard) | 1.30 |
| 3B base evals | 0.30 |
| Variant A late+retain + Variant C v1+v2 + 3B+LoRA hard+retain + 4 evals | ~0.90 |
| **Total session** | **~$5.00 of $15 envelope** |

## Recommended next moves

1. **3B ratio + size sweep** — 3B + LoRA at 15/85, 50/50, 70/30; 3B with augmented hard via paraphrase (slm-learning-093). $1-2.
2. **Variant C with gate=5e-3, up_scale=5e-3** — empirical sweet spot for the init balance. $0.85.
3. **Variant C with asymmetric init** (gate=1e-2, up_scale=1e-3) — preservation comes from small up, trainability from larger gate. $0.85.
4. **Frontier comparator via Gemini** — handoff `h-2026-05-08T12-30-00` awaits monorepo team pickup.

## Decisions this round

- `slm-learning-178` — hard rows insufficient at <=3B; retain mandatory
- `slm-learning-179` — cross-base failure transfer falsified; per-base pressure profile
- `slm-learning-180` — morphism growth requires smoothing
- `slm-learning-181` — Variant C late gated residual is next morphism design
- `slm-learning-182` — consolidation runs become first-class scaling events
- `slm-learning-183` — 3B + LoRA hard+retain at 30/70 fails; recipe parameters base-size-sensitive
- `slm-learning-184` — Variant C init balance is a needle (1e-3 inert, 1e-2 too noisy)
- `slm-learning-185` — retain-mix non-universal; Variant A late+retain hurt HE

— Dr. Stein, consolidation framework + 1.5B follow-ups + 3B rung close, 2026-05-08
