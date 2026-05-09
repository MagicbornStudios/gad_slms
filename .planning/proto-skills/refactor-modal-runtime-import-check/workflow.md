# workflow — refactor-modal-runtime-import-check

## When this fires

A refactor PR (or a pending commit) that touches Modal app code under
`modal_app/` (or wherever Modal `@app.function`-decorated files live) AND
introduces a new cross-module import within that package. Specifically:

- Any change that adds `from modal_app.<sibling> import ...` inside a
  function body or at the top of a `modal_app/` file.
- Any change that splits a previously-inlined helper into a sibling
  module within a Modal app package.
- Any commit that touches a file containing `@app.function(image=...)`
  decorators AND simultaneously edits the `image = (...)` builder.

## The bug pattern

Local Python with `sys.path` rooted at the project lets any sibling-
module import work. Modal does NOT inherit your local `sys.path`. It
ships only the files specified by `image.add_local_python_source(...)`,
plus `pip_install` packages. If a refactor extracts a helper into a
sibling module without updating the image's local-source list, you get:

```
ModuleNotFoundError: No module named 'modal_app'
```

at runtime, AFTER you've already paid for container startup (~20 seconds
of A10G time per failed fire). The local smoke test does not catch this
because `sys.path` resolves the import locally.

## The fix

Every Modal app file (`modal_app/*.py`) that imports from sibling modules
in the same package MUST have, in its image builder:

```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(...)
    .add_local_python_source("modal_app")  # <-- this line
)
```

This ships the entire `modal_app/` directory as a Python package onto
the container. The local smoke test still passes; the Modal runtime
now has the package available.

For the slm-learning case, the fix landed in commit a1ac3cf:

```diff
 image = (
     modal.Image.debian_slim(python_version="3.11")
     .pip_install(...)
+    .add_local_python_source("modal_app")
 )
```

## Static check (cheap, fast)

For every `*.py` file under `modal_app/`:

1. Detect `image = (...)` builder pattern (regex on the assignment).
2. Detect cross-module imports that target the package itself:
   `^\s*from modal_app\.\w+ import` and `^\s*import modal_app\.\w+`.
3. If imports of the package exist in the file but `add_local_python_source('modal_app')` is NOT in the image builder — emit a BLOCKING lint error.
4. Same check for any other detected app-level package (any subdir
   containing `__init__.py` or namespace-package layout that contains a
   `*.py` file with `@app.function`).

A simple Python script can run this as part of pre-commit or a CI step:

```python
import ast, pathlib, re

def check_modal_file(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    pkg = path.parent.name
    has_cross_import = bool(re.search(rf'^\s*(from\s+{pkg}\.\w+|import\s+{pkg}\.\w+)', text, re.MULTILINE))
    has_local_source = f'add_local_python_source("{pkg}")' in text or f"add_local_python_source('{pkg}')" in text
    has_app_function = '@app.function' in text or '@app.local_entrypoint' in text
    if has_app_function and has_cross_import and not has_local_source:
        return [f'{path}: imports from {pkg}.* but image lacks add_local_python_source({pkg!r})']
    return []
```

## Runtime smoke (definitive)

A tiny `@app.function` that does NOTHING but the imports + return `'OK'`:

```python
@app.function(image=image, timeout=120)
def import_smoke() -> str:
    """Verify cross-module imports survive the Modal package boundary."""
    # Trigger every cross-module import the real functions use:
    from modal_app.morphism_layers import IdentityProjectionLayer  # noqa: F401
    from modal_app.morphism_insertion import expand_with_identity   # noqa: F401
    from modal_app.eval_adapter import _judge                       # noqa: F401
    return "OK"
```

Run with:

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m modal run modal_app/<file>::import_smoke
```

Container startup is ~20s on a CPU-only function (no GPU needed). Cost
is roughly $0.005 per check vs ~$0.10 for a failed real fire (and the
operator-time cost of chasing the bug is much larger).

A passing smoke confirms the image ships every imported sibling module.

## Decision tree

```
Did the refactor add cross-module imports inside a Modal app file?
  No  → safe (no Modal package boundary affected); skip
  Yes:
    Does the image have add_local_python_source('<pkg>')?
      Yes → safe to ship; recommended: still run import_smoke once
      No  → BLOCK PR merge:
              1. add the line to the image builder
              2. run import_smoke to confirm
              3. only then merge
```

## Skill workflow (concrete steps an agent should run)

1. Identify Modal app files modified in the current diff:
   `git diff --name-only HEAD~1..HEAD | grep '^modal_app/'`
2. For each, run the static check from above. Block if any fail.
3. Author or update an `import_smoke` `@app.function` in any file that
   gained new cross-module imports.
4. Run `import_smoke` on Modal. Block until it returns `'OK'`.
5. Only after both pass, allow the merge / proceed to commit.

## Failure modes to recognize

- `ModuleNotFoundError: No module named '<pkg>'` from a Modal traceback
  pointing at a refactor-introduced import line → this skill missed.
- `Cannot find local source` errors from the Modal CLI during deploy →
  the package name in `add_local_python_source` doesn't match an
  importable directory; check spelling.
- A test that passes locally but fails on Modal with import errors →
  always check the image builder before debugging anything else.

## What to avoid

- Inlining helper class definitions back into the Modal file just to
  avoid the boundary. The whole point of refactor wave 1 was to
  eliminate duplication — fix the image config, don't re-duplicate.
- Setting `sys.path` from inside a `@app.function`. Modal doesn't ship
  your local tree; sys.path manipulation cannot recover what the
  container doesn't have.
- Skipping the runtime smoke because the static check passed. Static
  check covers the common case; runtime smoke catches subtle issues
  (e.g. a sibling that imports a package outside `modal_app/` that's
  not pip-installed).

## Acceptance test for this skill

After installing/promoting:

1. The exact failure pattern from refactor wave 1 (commit f8bd6bb)
   cannot recur — the static check would have flagged it.
2. Future Modal-app-package refactor PRs are gated by the static check.
3. Cost ledger shows zero failed-Modal-fire entries attributable to
   refactor-introduced import bugs.
4. New project initialized via `gad init` includes this skill in its
   pre-commit hook by default if `modal_app/` is detected.

## Refs

- `.planning/ERRORS-AND-ATTEMPTS.xml` error
  `refactor-introduced-modal-import-bug-2026-05-08`
- Commit `a1ac3cf` (the fix)
- Commit `f8bd6bb` (the refactor that introduced the bug)
- Positive example: `modal_app/eval_morphism.py` (HAS the line all along)
- `reports/research/reuse_one_file_per_concern_audit.md` (the audit
  that triggered refactor wave 1; future similar audits should
  reference this skill BEFORE shipping changes)
