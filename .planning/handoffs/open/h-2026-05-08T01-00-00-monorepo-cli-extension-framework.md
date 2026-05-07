---
id: h-2026-05-08T01-00-00-monorepo-cli-extension-framework
projectid: slm-learning
phase: 04
task_id: SL-T-04-cli-extensions
created_at: 2026-05-08T01:00:00.000Z
created_by: dr-stein-slm-learning
claimed_by:
claimed_at:
completed_at:
priority: high
estimated_context: bounded
risk: safe
time: standard
surface: cross-project
runtime_preference: claude-code
recipient: monorepo / platform team dispatcher (Marshal-tbd)
---

# Cross-project handoff — Project-scoped CLI extensions framework

From: Dr. Stein, slm-learning root
To: monorepo/platform team's dispatcher
Why: Operator declared a strategic shift away from one-off scripts
toward project-extensible CLI commands. They asked me to "start
extending using the idea for now" while the monorepo team builds the
framework. This handoff captures slm-learning's adopted shape so the
framework can be designed around real usage, not hypothetical.

Operator quote (verbatim, 2026-05-08):

> "we should have some dynamic way of extending our gad cli so we can
> use commands and stuff per project and have the projects extend
> the commands of the cli. rather than looking like we have one off
> scripts like this. this way the concept of scripts might not even
> exist really in the future as we will shed one-off commands that
> are scripts during our evolution process. we can do that. it would
> be a good signal to refactor and reorganize. […] the monorepo
> agent will make sure the framework and project support it. you
> should start extending using the idea for now."

## §1 — slm-learning's adopted shape

I've added `.planning/cli/extensions.json` registering the 4 commands
this project needs today:

| Command | Status | Why |
|---|---|---|
| `gad slm eval classify-failures` | wraps `scripts/eval/classify_humaneval_failures.py` | Diagnostic — buckets HumanEval failures into 9 categories |
| `gad slm eval aggregate-public-matrix` | wraps `scripts/eval/aggregate_public_matrix.py` | Report — compiles comparator-matrix public row |
| `gad slm data prepare-ocr-variants` | wraps `scripts/data/prepare_ocr_variants.py` | Data prep — builds 5 OCR variants for controlled experiments |
| `gad slm eval modal-fire` | planned | Wraps modal_app/eval_adapter with project-standard args; encodes bug-tax lessons (MSYS_NO_PATHCONV, dataset_limit, etc.) |

Manifest schema is documented at `.planning/cli/extensions.json` —
each entry has `name`, `module` (path), `entrypoint`, `description`,
`args[]`, `tags`, `decision_refs`. Forward-compatible with whatever
loader the framework lands.

## §2 — Design questions for the framework

Operator said you'd be designing it. Dr. Stein's open questions (vote
where you have a strong opinion):

| Question | Dr. Stein's lean |
|---|---|
| Discovery — does `gad --help` show project-extensions when run from a project root, or only via `gad <projectid> ...`? | **Project-root auto-discovery.** Run `gad --help` from `slm_learning/` and you see `slm` as a subcommand-namespace. Otherwise operators won't remember the namespace prefix |
| Namespace conflicts — what if two projects both register `slm eval ...`? | **Project-id resolves first**, so `gad slm-learning slm eval classify-failures` is unambiguous. The shorter `gad slm eval ...` works only when one project's namespace claims `slm` |
| Sandbox/safety — extensions can run arbitrary Python. Lock down? | **Cosign-style trust file**: the project root must include the extension paths in a `cli_extensions_trusted.txt` to allow execution. Rejects unsigned extensions with a one-line warning |
| Loader mechanism — entrypoint path is "module.py:function" — how do args flow? | **`argparse`-compatible `args` list in the manifest** that the loader translates into CLI flags. Module's `main(argv: list[str]) -> int` is the contract |
| Output channel — do extensions get the `gad state log`/handoff/notes integration for free? | **Yes via `from gad import state, handoffs, notes` injected as a project-cli SDK.** Otherwise every extension reinvents this and we drift |
| Sheddable extensions — operator mentioned "we will shed one-off commands". How? | **Manifest entries can have `status: "deprecated"` or `expires_after: <ISO>`. `gad evolution shed` includes them in the dry-run.** Aligns with existing `gad evolution shed` infrastructure |

## §3 — What slm-learning is doing in the meantime

Until the framework lands:

- New "scripts" go into `scripts/` AND are registered in
  `.planning/cli/extensions.json`. Path-based for now; loader-based
  when framework lands.
- Operators run them as `.venv/Scripts/python.exe <module> --args`
  today. The manifest documents the future invocation
  (`gad slm <subcommand>`).
- I will NOT add new files to `scripts/` without registering them in
  the manifest. That's the "extension-first authoring policy" I'd
  like to register as `slm-learning-108`.

## §4 — Non-goals for this handoff

- Don't implement the loader inside this handoff — that's the
  framework lane.
- Don't backfill existing `scripts/` files into the manifest unless
  they're current. Many are dead/deprecated.
- Don't ship the framework on a deadline. The slm-learning research
  loop continues working with the path-based fallback.

## §5 — Slm-learning's commitments

- Continue authoring new commands in the manifest format.
- Update existing manifest entries when the loader API solidifies
  (e.g. switch `module: "scripts/x.py"` to
  `module: "slm_learning.cli.x"` when there's a Python package).
- Provide live usage data — what commands operators actually use,
  what flags, what fails — to inform the framework design.

## §6 — Decision proposed

Once the loader lands, slm-learning files `slm-learning-108`:

> **Extension-first authoring policy.** Every new project-specific
> command is authored as a `.planning/cli/extensions.json` entry,
> not a free-floating script. Old scripts are treated as legacy
> debt; `gad evolution shed` flags them when their manifest entry is
> missing or deprecated.

## Acceptance gate

Receiving lane (monorepo dispatcher / Marshal-tbd):

- [ ] Reply with the loader API shape (call signature, SDK injection,
      args translation). Slm-learning will adopt within one phase.
- [ ] Decide on namespace conflict resolution.
- [ ] Decide on the trust/safety mechanism for arbitrary extensions.
- [ ] Closeout handoff when the loader is live; slm-learning will
      then file `slm-learning-108`.

— Dr. Stein
