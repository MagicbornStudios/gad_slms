# Troubleshooting — build-and-release-locally

Detailed debug paths moved out of SKILL.md for token efficiency. Most
operators never read this — only consulted when the specific failure
appears.

## Historical note (2026-04-22 cleanup)

This file previously documented Node SEA + postject failure modes
(sentinel collision, .node loader issues). Those are obsolete after
decision gad-278 migrated the build pipeline to `bun build --compile`.
The SEA code paths, scripts (`build-release.mjs`,
`build-release-support.mjs`), and dependency on `postject` are gone.

If an agent is trying to diagnose a SEA-era error message, they are
almost certainly running an outdated skill copy — the canonical build
skill was rewritten 2026-04-22. Re-install via `gad install all
--<runtime>` from the current vendor checkout.

## `bun build: couldn't resolve ...`

Bun's static analyzer cannot trace dynamic `require(...)` patterns with
computed paths. `bin/commands/*.cjs` is dynamically loaded via a
discovery loader in `bin/gad.cjs`, so the compiler needs a static
require manifest to know which files to bundle.

**Fix:** `scripts/build-manifest.mjs` runs as a pre-bundle step in
`scripts/build-bun-release.mjs`. It enumerates `bin/commands/*.cjs` and
emits a static require manifest consumed by bun's compile pass. If you
see the resolve error, verify the manifest step is running first and
that the emitted manifest file exists before `bun build --compile` is
invoked.

## Exe reports stale version

Bun's compile cache can retain a prior build's artifacts when
package.json version bumps without source changes in `bin/gad.cjs`.

**Fix:** `rm -rf dist/ node_modules/.cache && npm run build:release`
forces a clean rebuild. `scripts/build-stamp.mjs` freezes git SHA + src
hash into the compiled binary — if those change, the build is fresh.

## TUI binary missing from release

`scripts/build-bun-release.mjs` soft-invokes `pnpm --filter
@magicborn/gad-tui build:bun`. If the TUI build fails, the CLI release
still succeeds and ships without the TUI.

**Fix:** Run the TUI build directly to see the real error:

```sh
pnpm --filter @magicborn/gad-tui build:bun
```

Tracked as task 63-48 (wire into CI) and 63-50 (unify into single
binary — eliminates this failure mode entirely).

## `gh release create` fails with 422 on re-upload

Previous run uploaded bad artifacts under the same tag.

**Fix:** `gh release upload <tag> <files> --clobber` overwrites. The
`scripts/publish-release.mjs` helper uses `--clobber` by default.

## Windows Defender / SmartScreen blocks the exe

The release binaries are unsigned. Defender heuristic-flags them on
first run.

**Fix (consumer):** Right-click the exe → Properties → Unblock →
Apply. Code-signing certificates are a HUMAN-TODO not yet addressed.

## Build succeeds but binary won't launch on target OS

Cross-compiled bun binaries occasionally have native-module linking
issues. `bun build --compile` handles most cases but some native deps
(e.g. sharp, onnxruntime) embed platform-specific .node files that
don't cross-compile cleanly.

**Fix:** Build on the target OS directly, OR list the problematic
module in bun's externals and provide the .node file alongside the
release. For GAD today, embeddings (@huggingface/transformers +
onnxruntime) are intentionally excluded from the release binary — the
packaged CLI falls back to Jaccard ranking for snapshot.
