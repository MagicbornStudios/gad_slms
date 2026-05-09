---
name: refactor-modal-runtime-import-check
description: >-
  Whenever a refactor adds cross-module imports inside Modal @app.function
  files, the image config must have .add_local_python_source('<pkg>') OR
  a runtime import_smoke @app.function must pass. Local smoke tests do
  not catch the Modal package boundary because sys.path resolves locally.
  Static lint + tiny runtime smoke ($0.005) prevent expensive failed
  fires (~$0.10 each) and operator-chase-time of refactor-introduced
  ModuleNotFoundError.
status: proto
workflow: ./workflow.md
---

Refactor wave 1 (commit f8bd6bb) eliminated 319 LOC of duplication and
passed every local smoke test bit-identical — and then crashed on Modal
with `ModuleNotFoundError: No module named 'modal_app'` because the
extracted-into-sibling-module imports were not shipped to the container.
The image builder needed `.add_local_python_source('modal_app')`. This
skill captures the static check (block PRs that add cross-module imports
to Modal app files without updating the image) and the runtime smoke
pattern (a $0.005 `@app.function` that just runs the imports). Promoting
to framework-level because every Modal-using project's refactor PR is
at risk.

**Workflow:** [./workflow.md](./workflow.md)

## Provenance

- Source candidate: `.planning/candidates/refactor-modal-runtime-import-check/CANDIDATE.md`
- Drafted: 2026-05-09 by `create-proto-skill`
- Lock marker: see `./PROVENANCE.md`
- Error of record: `refactor-introduced-modal-import-bug-2026-05-08`
- Fix commit: `a1ac3cf`
- Bug-introducing commit: `f8bd6bb`
