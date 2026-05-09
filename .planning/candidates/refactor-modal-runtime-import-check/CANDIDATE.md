# Candidate: refactor-modal-runtime-import-check

**Priority:** HIGH (framework-level — every Modal-using project benefits)
**Source pressure:** session 2026-05-08, slm-learning, commit f8bd6bb (refactor wave 1)
**Bit us:** 1× this session, real cost (~$0.10 in failed-fire compute)
**Refs:** error `refactor-introduced-modal-import-bug-2026-05-08`, slm-learning-196 (reuse audit that triggered the refactor)

## Trigger

Any refactor that extracts shared modules used by Modal `@app.function` files. Specifically:

- Any change that introduces a new `from <pkg>.<module> import ...` inside a function body or at the top of a `modal_app/` file.
- Any change that splits a previously-inlined helper into a sibling module within a Modal app package.
- Any refactor PR that touches a file containing `@app.function(image=...)` decorators.

## The bug pattern (what we're guarding against)

Local Python with `sys.path` set to the project root makes any sibling-module
import work. Modal does NOT have your local sys.path — it ships the
files specified by `image.add_local_python_source(...)` and that's all
the package-namespace it has on the container.

If you refactor `modal_app/train.py` to import `from modal_app.helpers import foo` but the image config doesn't have `.add_local_python_source('modal_app')`, the local smoke test passes (sys.path picks up the dev tree) but the Modal job fails with `ModuleNotFoundError: No module named 'modal_app'` AFTER you've paid for container startup.

Cost: every failed fire is a couple of cents in container-init time, plus operator time chasing the bug.

## Concrete failure (2026-05-08)

Refactor wave 1 (commit f8bd6bb) extracted morphism layers + insertion helper into `modal_app/morphism_layers.py` + `modal_app/morphism_insertion.py`. Three callers updated:

- `modal_app/train_morphism.py` ← imports broken on Modal
- `modal_app/eval_morphism.py` ← imports OK on Modal (had `add_local_python_source('modal_app')` already)
- `scripts/morphism/local_init_smoke_test.py` ← imports OK locally (sys.path manipulation)

Local smoke test (all 3 variants A/B/C) passed bit-identical. Then 2 Variant C arms fired on Modal and crashed:

```
/root/train_morphism.py:124 in _train_morphism_inner
> 124 from modal_app.morphism_insertion import expand_with_identity
ModuleNotFoundError: No module named 'modal_app'
```

Fix in commit a1ac3cf: add `.add_local_python_source('modal_app')` to train_morphism.py's image config.

## Skill body

The skill should provide a pre-PR check + a smoke template:

### Static check (cheap, fast)

For every `*.py` file in `modal_app/` (or wherever Modal apps live):
1. Find the `image = (...)` builder pattern.
2. If it imports from sibling modules (regex: `^from (modal_app|<pkg>)\.\w+ import` AND `^import (modal_app|<pkg>)\.\w+`), require the image to have `.add_local_python_source('<pkg>')`.
3. Lint: emit a warning if not present.

### Runtime smoke (definitive)

A tiny `@app.function` that does NOTHING but the imports + return `'OK'`:

```python
@app.function(image=image, gpu=None, timeout=120)
def import_smoke() -> str:
    # Trigger every cross-module import the real functions use:
    from modal_app.morphism_layers import IdentityProjectionLayer  # noqa: F401
    from modal_app.morphism_insertion import expand_with_identity  # noqa: F401
    from modal_app.eval_adapter import _judge  # noqa: F401
    return "OK"
```

Run with `modal run modal_app/<file>::import_smoke` before merging the refactor PR. Container startup is ~20s, so ~$0.005 per check vs ~$0.10 for a failed-real-fire.

### Skill workflow

1. Detect refactor commits touching Modal app files (e.g. via post-commit hook or PR check).
2. For each Modal file modified, list cross-module imports it now contains.
3. Verify image config has `add_local_python_source('<pkg>')` for the parent package.
4. If missing OR if any import looks new, run the runtime smoke. Block PR merge until smoke returns "OK".

## Decision tree for the skill

```
Did refactor add cross-module imports inside Modal app files?
  Yes -> Is .add_local_python_source(<pkg>) in the image?
           Yes -> safe to ship
           No  -> require ADD this line + run runtime smoke
  No  -> safe (no Modal package boundary affected)
```

## Files / locations the skill should reference

- `modal_app/eval_morphism.py` (positive example: HAS `.add_local_python_source('modal_app')`)
- `modal_app/train_morphism.py` (post-fix; was missing, now correct via commit a1ac3cf)
- `.planning/ERRORS-AND-ATTEMPTS.xml` error `refactor-introduced-modal-import-bug-2026-05-08`
- `reports/research/reuse_one_file_per_concern_audit.md` — the audit that triggered refactor wave 1; future refactors should reference this skill BEFORE the audit findings ship

## Acceptance test

After promoting:
1. Future Modal-app refactor PR with cross-module imports gets blocked by the static check until image config is updated.
2. Failing-real-fire bug from f8bd6bb cannot recur — runtime smoke catches it before any compute is spent.
3. Cost ledger shows zero failed-Modal-fire entries attributable to refactor-introduced import bugs.
