# Session evolution candidates — 2026-05-08

**Date:** 2026-05-08
**Owner:** Dr. Stein
**Trigger:** Operator signal "pressure is building up, level up and evolve."
**Decision refs:** slm-learning-201 (Variant C closed), 202 (3B sweep closed), 197-200 + 214-221 (canonical), forthcoming proto-skill drafting.

This session generated lessons that should become proto-skills next session.
Use as input to `gad evolution evolve` — the patterns are concrete enough
for autonomous proto-skill drafting.

## Candidates (priority order)

### 1. modal-cli-windows-prefix (HIGH — bit us 2× this session)

**Trigger:** Any Modal CLI invocation from Bash on Windows.
**Pattern:** Prepend BOTH `MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8` always.
**Why:**
- `PYTHONIOENCODING=utf-8` — Modal CLI prints `✓` checkmark which crashes cp1252 charmap. Without it, app registers but 0 tasks queue.
- `MSYS_NO_PATHCONV=1` — Git Bash MSYS rewrites leading-slash args (`/models/runs/.../adapter`) into `C:/Program Files/Git/...`. Without it, `--adapter-id` gets corrupted and HF/Modal fail with HFValidationError.
- Both bit us in the same session — first encoding (5 training arms registered, 0 tasks), then path translation (6 eval arms ran but failed validation).
**Skill body:** Decision tree — if PowerShell, just `$env:PYTHONIOENCODING = 'utf-8'`. If Bash, prepend both. If neither works, use absolute Windows paths.
**Refs:** Note `2026-05-08-modal-pyiconencoding-utf8-prefix.md`, error `msys-pathconv-translates-modal-volume-paths-2026-05-08`, slm-learning-105.

### 2. refactor-modal-runtime-import-check (HIGH — caused real cost)

**Trigger:** Any refactor that extracts shared modules used by Modal `@app.function` files.
**Pattern:** Add an `add_local_python_source('<package>')` to the image config OR run a tiny Modal-runtime smoke that imports + returns `'OK'` before the refactor PR lands.
**Why:** Local `sys.path` manipulation makes the smoke test pass. Modal's package boundary is different. Refactor wave 1 (commit f8bd6bb) had bit-identical class definitions and passing local smoke for all 3 variants — but `train_morphism.py` failed on Modal with `ModuleNotFoundError: No module named 'modal_app'` because the image didn't ship the package. Cost: ~$0.10 in failed-fire compute.
**Skill body:** Pre-PR checklist — every Modal app file that imports from sibling modules in the same package needs `.add_local_python_source(<package>)`. Verify with a smoke `@app.function` that just runs the imports.
**Refs:** Error `refactor-introduced-modal-import-bug-2026-05-08`.

### 3. registry-as-first-class-artifact (MEDIUM — pattern this session)

**Trigger:** Project accumulates implicit knowledge of datasets / model families / teachers / news that isn't queryable.
**Pattern:** Build version-controlled JSON registries with schemas + sync scripts + a news folder. Surface in TUI via `/registry` command.
**Why:** Replaces "we know about these datasets" with explicit rows. Foundation for routing, comparator selection, teacher policy. Implementation lives in `data/registry/` + `schemas/` + `scripts/registry/` + `news/`.
**Skill body:** When to introduce a registry — when ≥3 ad-hoc references to the same item appear in different docs, or when a routing decision needs to query "what models / datasets / teachers do we have." Schema → seed JSON → sync script → CI/CD or manual cadence.
**Refs:** slm-learning-198, decision body in `reports/research/teacher_species_policy.md`.

### 4. teacher-roles-six-way-split (MEDIUM — methodology pattern)

**Trigger:** Any framing that conflates "teacher" with multiple roles.
**Pattern:** Split into 6 named roles: teacher (gold labels), bulk_labeler (cheap volume), backbone (the body we train), truth (verifiers), inspector (logit research), comparator (paper repro). Each model fills 1-3 roles.
**Why:** ChatGPT-block proposed "Qwen-80B as teacher peer to Opus" — actually Qwen-80B is a great labeler/comparator/inspector but NOT a teacher rival. The conflation collapsed the planning surface. Splitting clarified which model gets which role for which task_shape.
**Skill body:** Apply when proposing a new model adoption, designing an eval comparator, or building a routing policy. Six-role checklist forces explicit role assignment per model.
**Refs:** slm-learning-197, `reports/research/teacher_species_policy.md`.

### 5. trace-json-to-delta-packet-pipeline (MEDIUM — replicable Kael pattern)

**Trigger:** Sibling project produces TRACE.json files of failed agent trajectories.
**Pattern:** Walk TRACE.json files → filter by composite/human_review thresholds → categorize failure types → derive minimal_prompt + correction (peer or hand-written) → emit delta packets per `schemas/delta_packet.schema.json` against a context_root → assemble retain bank from positives.
**Why:** Pressure → training data conversion. The Kael-house dataset (10 packets + 4 retain rows) demonstrates the pattern end-to-end. Reusable for any sibling project that produces eval traces.
**Skill body:** Build script template + filter rules + failure taxonomy + context_root proposal + retain bank fields. Adapter to add for each new project: failure-category mapping + retain-bank schema fields.
**Refs:** slm-learning-167, 186, 189, 191, 193, scripts/data/build_kael_house_dataset.py, reports/research/kael_house_dataset_scoping_2026-05-08.md.

### 6. lane-closure-via-clean-falsification (MEDIUM — discipline pattern)

**Trigger:** A research lane is hypothesized to lift; experiments come back inert/regressing.
**Pattern:** Test ≥3 hyperparameter regimes covering the space. If all regress or are inert, log a decision titled "<lane> CLOSED" with refutation across the range. Don't keep adding more variants — the lane is closed.
**Why:** Variant C had three init regimes tested (1e-3 inert, 1e-2 noisy, 5e-3 + asymmetric inert). Decision 201 closed it. 3B ratio sweep had three retain ratios tested (15/85, 50/50, 70/30); all regress HE. Decision 202 closed it. Without explicit lane-closure decisions, we'd keep retrying variants forever.
**Skill body:** Falsification protocol — define the lane, define what would constitute clean refutation, run the experiments, log the decision with the result table, move on. Resists "just one more variant" trap.
**Refs:** slm-learning-201, slm-learning-202, slm-learning-184, slm-learning-185.

### 7. subagent-with-quoted-operator-direction (LOW — workflow pattern)

**Trigger:** Operator provides a long ChatGPT-paired discussion + "what to tell Claude" copy/paste block.
**Pattern:** Dispatch a subagent with the operator's authoritative direction quoted verbatim, plus context (existing schemas, decision IDs, related artifacts). Subagent produces deliverables; Dr. Stein reviews + commits + logs decisions.
**Why:** Two subagents this session each produced 6-7 polished artifacts (~950+1670 lines) in ~7 min from a single Dr. Stein dispatch. The verbatim quote is load-bearing — it preserves operator intent across the agent boundary.
**Skill body:** Dispatch template with sections (operator direction verbatim, deliverables list, existing context to align with, constraints, format, report). Score against `docs/handoff_prompt_quality.md` rubric (≥12/16).

## Summary

| # | Candidate | Priority | Status |
|---|---|---|---|
| 1 | modal-cli-windows-prefix | HIGH | Note exists, ready for proto-skill draft |
| 2 | refactor-modal-runtime-import-check | HIGH | Error logged, ready for proto-skill draft |
| 3 | registry-as-first-class-artifact | MEDIUM | Pattern shipped, ready to formalize |
| 4 | teacher-roles-six-way-split | MEDIUM | Doc shipped, ready to formalize |
| 5 | trace-json-to-delta-packet-pipeline | MEDIUM | Build script shipped, ready to formalize |
| 6 | lane-closure-via-clean-falsification | MEDIUM | Two examples now (Variant C + 3B sweep), ready |
| 7 | subagent-with-quoted-operator-direction | LOW | Pattern demonstrated, low priority |

## Next session

Run `gad evolution evolve --projectid slm-learning` and feed this list as input. Top 2 candidates (Modal prefix + refactor-Modal-runtime check) deserve framework-level promotion since they affect every Modal-using project, not just slm-learning.

— Dr. Stein, session-end evolution candidates, 2026-05-08
