---
name: build-and-release-locally
description: Cut a new GAD release — version bump, CHANGELOG entry, `bun build --compile` rebuild, git tag, and `gh release create` with artifacts attached. Operator-triggered only, no CI, no npm publish. Trigger this skill whenever the user asks to "cut a release", "ship v<N>", "publish a new release", "bump the version", or any variation that means "the canonical GAD repo should have a new downloadable installer artifact on GitHub Releases." Canonical-repo-only: refuses to run outside the MagicbornStudios/get-anything-done clone. See decisions gad-188 (distribution is GitHub Releases + executable download, no GitHub Actions), gad-278 (bun build --compile is canonical), gad-279 (gad-129 superseded, no public npm).
lane: prod
type: captured-answer
---

# build-and-release-locally

This is the procedure for cutting a GAD release from the operator's workstation. There is no CI. There is no `npm publish`. The only distribution channel is GitHub Releases on `github.com/MagicbornStudios/get-anything-done`, and the only way to populate it is to run this skill end-to-end on a machine that has Node, `gh`, and `git` installed, with push access to the canonical repo.

## When to trigger this skill

- User asks to "cut a release", "ship v<N>", "publish a new release", "bump the version to <N>".
- Task 44-31 or any downstream Track B installer task (44-32/33/34) is blocked waiting for a release to exist.
- CHANGELOG `[Unreleased]` section has accumulated enough material to warrant a new version, and the user confirms they want to publish.
- A downstream consumer (eval runner, someone installing GAD into their repo) needs a fresh `installer.exe` and the last published release is materially stale.

## When NOT to trigger this skill

- In-progress work on a feature branch — releases come from `main` after the work is merged.
- When `dist/release/gad-v*.exe` is already current and only docs or planning changed — a release is not required for every commit.
- When running inside a consumer project (the canonical-repo gate will refuse).
- When the user asks to publish to npm — GAD does not ship to npm. Explain and refuse.

## Hard gates before you start

1. **Canonical repo check.** Run `git config --get remote.origin.url` and confirm it matches `MagicbornStudios/get-anything-done(.git)?`. If not, refuse: the operator is in a consumer project and this skill cannot run.
2. **Branch check.** Confirm `git branch --show-current` is `main` and `git status --porcelain` is empty. Releases come from a clean `main`. If there are uncommitted changes, list them and stop — the operator decides whether to commit/stash/discard before you proceed.
3. **Tool availability.** Confirm `node --version`, `gh --version`, and `git --version` all return. If `gh` is missing or unauthenticated (`gh auth status`), stop and print the install/auth instructions.
4. **Fetch.** Run `git fetch --tags` so local tag state matches the remote. If a tag with the target version already exists, refuse — version bumps must be monotonic.
5. **Dependencies.** Run `npm install` (or confirm `node_modules/` is up to date). Bun must be on PATH — `bun --version` should return `>=1.3.11`. The release build shells out to `bun build --compile`.

## Procedure

### Step 1 — Decide the new version

Read `package.json` `version` field and propose the next version following semver:

| Change type | Bump |
|---|---|
| Breaking CLI surface, removed commands, schema renames | MAJOR |
| New commands, new subcommands, new decisions, new skills | MINOR |
| Bug fixes only, no new surface | PATCH |

Confirm the chosen version with the operator before editing files. The operator can override.

### Step 2 — Bump version in package files

Edit both:

- `package.json` — update `version` field
- `package-lock.json` — update BOTH top-level `version` AND the `packages[""].version` field

Use the `Edit` tool, not a manual `npm version` call — npm version creates a commit + tag unprompted, which collides with this skill's control flow.

### Step 3 — Write the CHANGELOG entry

Edit `CHANGELOG.md`. Keep the structure:

```
## [Unreleased]

## [<new-version>] - <YYYY-MM-DD>

<one-paragraph summary of the release>

### Added
- …

### Changed
- …

### Fixed
- …

### Contract notes (optional)
- …
```

Source material: `git log --oneline <previous-tag>..HEAD` if there is a previous tag, or `git log --since=<previous-release-date> --oneline` if not. Group commits by subsystem (CLI, site, framework, release pipeline, eval framework). Cite decision IDs (`gad-NNN` / `GAD-D-NNN`) and task IDs (`NN-NN` / `GAD-T-NN-NN`) where relevant — the changelog is a primary durable record of WHY changes happened.

Keep it concise but thorough. A release with 300+ commits warrants a long changelog section; a patch release warrants 5 lines.

### Step 4 — Rebuild the release artifact

```sh
npm run build:release
```

This runs `scripts/build-bun-release.mjs` which:

1. Calls `scripts/build-manifest.mjs` — generates the static require manifest so `bun build --compile` can statically trace `bin/commands/*.cjs` modules.
2. Calls `scripts/build-stamp.mjs` — freezes git SHA + src hash into the exe so `gad version` reports correctly from the compiled binary.
3. Soft-invokes `pnpm --filter @magicborn/gad-tui build:bun` — builds the TUI binary into `packages/gad-tui/dist/gad-tui-<platform>.exe` and copies it to `dist/release/gad-tui-v<version>-<platform>-<arch>.exe`. If the TUI build fails, it warn-skips and the CLI release ships without the TUI (a known gap tracked as task 63-48 / 63-50).
4. Runs `bun build --compile --target=bun-<platform>-<arch>` on `bin/gad.cjs` and outputs `dist/release/gad-v<version>-<platform>-<arch>.exe`.
5. Writes `dist/release/INSTALL.txt` with the correct artifact name and invocation instructions (single-file exe, no external runtime required).

Cross-platform note: `build-bun-release.mjs` runs bun's cross-compile via `--target=bun-<platform>-<arch>` flags, so one machine can produce artifacts for Windows / macOS / Linux. Matrix: `{windows,macos,linux} x {x64,arm64}`. To build for a non-host platform, pass `--platform` / `--arch` flags to the script.

**Verify the build** before committing:

```sh
ls -la dist/release/
./dist/release/gad-v<version>-windows-x64.exe --version    # on Windows
./dist/release/gad-v<version>-<platform>-<arch> --version  # on macOS/Linux
```

The version output must match the version you just bumped to. If it reports the old version, the bun cache did not invalidate — run `rm -rf dist/ && npm run build:release` to force a clean rebuild.

### Step 5 — Commit the release

```sh
git add package.json package-lock.json CHANGELOG.md
git commit -m "release: v<version>"
```

Do NOT commit `dist/` — it is gitignored. The artifact lives only in GitHub Releases.

### Step 6 — Tag

```sh
git tag -a v<version> -m "GAD v<version>"
```

Annotated tag, not lightweight — the tag message is what `gh release create --generate-notes` picks up if no `--notes-file` is given.

### Step 7 — Push commit + tag

```sh
git push origin main
git push origin v<version>
```

Submodule consumers: push from INSIDE the submodule. Outer repo's submodule pointer is a separate follow-up commit.

Tag push is the point of no return — confirm with the operator before pushing. Deleting a published tag breaks downstream consumers.

### Step 8 — Create the GitHub release

```sh
npm run publish:release
```

This runs `scripts/publish-release.mjs` which:

1. Reads the current `package.json` version and derives `v<version>` as the tag.
2. Runs `npm pack --pack-destination dist/release` if `dist/release/` does not already contain `get-anything-done-<version>.tgz`.
3. Checks `gh release view v<version>` — if the release already exists, skips the create step.
4. Otherwise runs `gh release create v<version> --title "GAD v<version>" --generate-notes`.
5. Uploads every artifact in `dist/release/` matching `gad-v*`, `get-anything-done-*.tgz`, `install-gad-windows.ps1`, or `INSTALL.txt` via `gh release upload --clobber`.

`--clobber` means re-running the skill after fixing a bad artifact is safe: the upload replaces the existing asset at the same name.

**Alternative**: to attach a richer body than `--generate-notes`, pass `--notes-file` pointing at a temporary file containing the CHANGELOG section you wrote in step 3:

```sh
node scripts/publish-release.mjs --notes-file /tmp/release-notes-v<version>.md
```

### Step 9 — Verify

```sh
gh release view v<version>
gh release view v<version> --json assets --jq '.assets[].name'
```

Confirm the tag exists, the title is correct, and every expected artifact is attached (`gad-v<version>-<platform>-<arch>`, `get-anything-done-<version>.tgz`, install helper files). Open the URL in a browser if the operator wants a visual check:

```sh
gh release view v<version> --web
```

### Step 10 — Update planning docs

Edit `.planning/STATE.xml` `<next-action>` to reflect that the release is cut. If the release closes a task, update `.planning/TASK-REGISTRY.xml` — set `status="done"`, `skill="build-and-release-locally"`, `agent="default"`, `type="framework"`. Capture any new decisions in `.planning/DECISIONS.xml` (e.g. version cadence policy, what went into the release notes).

Commit the planning-doc updates separately from the release commit — the release commit should be minimal (version files + CHANGELOG only).

## Common failure modes

| Failure | Cause | Fix |
|---|---|---|
| `bun: command not found` | Bun not on PATH | Install bun: `npm install -g bun` or `curl -fsSL https://bun.sh/install \| bash` |
| `bun: version too old` | Bun <1.3.11 | Upgrade bun: `bun upgrade` |
| `gh: command not found` | `gh` CLI not installed | Install from `https://cli.github.com` |
| `gh auth status: not logged in` | `gh` not authenticated | Run `gh auth login`, pick HTTPS or SSH, follow the prompts |
| Release exists, upload fails with 422 | Previous run uploaded bad artifacts | `gh release upload <tag> ... --clobber` (already the default in `publish-release.mjs`) |
| Exe reports old version after rebuild | Stale bun build cache | `rm -rf dist/ node_modules/.cache && npm run build:release` |
| TUI not in release | `pnpm --filter @magicborn/gad-tui build:bun` soft-skipped (bun version, missing workspace package, etc.) | Fix the underlying TUI build issue; tracked as task 63-48 (CI) + 63-50 (unify to single binary) |
| `bun build: error: couldn't resolve ...` | Dynamic require pattern opaque to bun's static analysis | Check `scripts/build-manifest.mjs` is emitting the static manifest before bun compile |
| Tag push rejected | Someone else tagged first, or local is behind | `git pull --rebase origin main && git fetch --tags` and re-verify version |
| Build-release succeeds but exe won't launch on Windows | Windows Defender or SmartScreen blocked an unsigned binary | Expected for unsigned releases; instruct consumers to right-click → Properties → Unblock. Code-signing is a separate decision not covered here. |

## Contract with 44-28 umbrella

This skill is the B0 foundation of the Track B installer pipeline (decision gad-188). Downstream tasks that depend on a consumable release:

- **44-32 / B2** — `bin/install.js` `--from-release <url|tag>` flag needs a real release to pull from.
- **44-33 / B3** — Site packaging produces a `site-<version>.zip` artifact uploaded alongside the installer.
- **44-34 / B4** — Portable Node bootstrap ships a `node-v<N>-<platform>.zip` artifact uploaded alongside the installer.

Every one of those downstream tasks **adds a new artifact** to the release. The shape of `publish-release.mjs`'s `getArtifacts()` filter (`/^gad-v.+/` + explicit install files) may need to widen when B2/B3/B4 land — revise this skill at that point.

## Guardrails — things this skill MUST NOT do

1. **Never run `npm publish`.** GAD is not on npm. If the operator asks, explain and refuse.
2. **Never trigger CI / GitHub Actions.** There is no CI. This skill is the only release path.
3. **Never force-push to `main`.** If the release commit fails a hook, fix the underlying problem and create a new commit — do not `git push --force`.
4. **Never delete a published tag.** If a release is bad, cut a new version that fixes it. Deleting published tags breaks downstream consumers.
5. **Never run outside the canonical repo.** The gate in step 1 is load-bearing. Consumer projects should use `gad skill promote --project` to equip skills, not this skill.
6. **Never push the tag without explicit operator confirmation in the conversation where the skill is running.** The `git push origin v<version>` step is the point of no return.
