"""Bootstrap doc-verifier training pairs from real markdown files.

The doc-verifier agent's job is deterministic: given a claim (file path,
function reference, command, dependency, API endpoint), check the live
codebase and return verified | refuted | unknown plus evidence.

We can ground-truth those claims directly by running the same checks the
agent would run. That gives us *bootstrapped-tier* training data —
programmatically grounded, reproducible, no LLM teacher required.

This sits alongside the schema in slm-learning-041:
    gold      = human-reviewed
    silver    = frontier agent + automated checks
    synthetic = haiku paraphrase / augmentation
    bootstrapped = THIS — deterministic ground truth from filesystem

Schema of each output pair (matches the gad-doc-verifier output contract):
    {
      "schema_version": "slm-learning-doc-verifier-pair@1",
      "input": {
        "doc_path": "<rel path>",
        "project_root": "<abs path>",
        "claim": "<extracted claim string>",
        "claim_category": "file_path | command | function | dependency | api_endpoint",
        "line": <int>
      },
      "output": {
        "claim": "<claim>",
        "status": "verified | refuted | unknown",
        "evidence": ["<file:line>", ...],
        "confidence": <float in [0,1]>,
        "reason": "<short rationale>"
      },
      "provenance": {
        "source_file": "<rel path>",
        "agent_type": "gad-doc-verifier",
        "input_context_hash": "<sha>",
        "timestamp": "<ISO>",
        "project_id": "<id>",
        "human_approved": false,
        "later_contradicted": false,
        "secret_redacted": <bool>,
        "data_tier": "bootstrapped"
      }
    }

Usage:
    .venv/Scripts/python.exe scripts/synth_doc_verifier_pairs.py \\
        --root . \\
        --root ../custom_portfolio \\
        --root ../grime_time_site \\
        --out data/agent_corpus_gad-doc-verifier.bootstrapped.jsonl \\
        --max-claims-per-doc 20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Reuse same secret patterns as the corpus extractor.
SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\bnpm_[A-Za-z0-9_\-]{30,}"), "[REDACTED_NPM_TOKEN]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "[REDACTED_GH_PAT]"),
    (re.compile(r"\bgh[ous]_[A-Za-z0-9]{30,}"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}"), "[REDACTED_GH_FINEPAT]"),
    (re.compile(r"\bAKIA[A-Z0-9]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "[REDACTED_HF_TOKEN]"),
]

EXTENSIONS = (
    ".ts", ".js", ".cjs", ".mjs", ".md", ".json", ".yaml", ".yml", ".toml",
    ".txt", ".sh", ".py", ".go", ".rs", ".java", ".rb", ".css", ".html",
    ".tsx", ".jsx",
)
EXT_RE = re.compile(
    r"`([a-zA-Z0-9_./\-]+(?:" + "|".join(re.escape(e) for e in EXTENSIONS) + r"))`"
)
FN_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*)\(\)`")
PKG_NPM_SCRIPT_RE = re.compile(r"`(?:npm run|yarn|pnpm run)\s+([a-zA-Z0-9_:\-]+)`")
DEP_PROSE_RE = re.compile(
    r"(?:uses|requires|depends on|powered by|built with)\s+`([a-zA-Z0-9_@/\-]+)`",
    re.IGNORECASE,
)

SKIP_LINE_PREFIXES = ("e.g.", "example:", "for instance", "such as", "like:")
SKIP_PATH_TOKENS = ("your-", "<", "{", "example", "sample", "placeholder", "my-")


def redact(text):
    if not text:
        return text, False
    redacted = False
    for pat, repl in SECRET_PATTERNS:
        new_text = pat.sub(repl, text)
        if new_text != text:
            redacted = True
            text = new_text
    return text, redacted


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def is_placeholder(token):
    low = token.lower()
    return any(t in low for t in SKIP_PATH_TOKENS)


def find_markdown_files(root: Path):
    seen = set()
    for p in root.rglob("*.md"):
        # Skip node_modules, .git, etc.
        parts = set(p.parts)
        if parts & {"node_modules", ".git", "dist", "build", ".next", ".venv", ".venv-gpu"}:
            continue
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        yield p


def extract_claims_from_doc(doc_path: Path, project_root: Path):
    """Return list of (line_no, category, claim_token)."""
    claims = []
    try:
        lines = doc_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return claims

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        low = stripped.lower()
        if any(low.startswith(p) for p in SKIP_LINE_PREFIXES):
            continue
        if "<!-- VERIFY:" in stripped:
            continue
        if "<!-- generated-by: gad-doc-writer -->" in stripped:
            continue

        for m in EXT_RE.finditer(line):
            tok = m.group(1)
            if is_placeholder(tok):
                continue
            claims.append((i, "file_path", tok))
        for m in FN_RE.finditer(line):
            tok = m.group(1)
            if is_placeholder(tok):
                continue
            claims.append((i, "function", tok))
        for m in PKG_NPM_SCRIPT_RE.finditer(line):
            tok = m.group(1)
            claims.append((i, "command", tok))
        for m in DEP_PROSE_RE.finditer(line):
            tok = m.group(1)
            if is_placeholder(tok):
                continue
            claims.append((i, "dependency", tok))
    return claims


def verify_file_path(claim, project_root: Path):
    target = (project_root / claim).resolve()
    if target.exists():
        rel = target.relative_to(project_root) if str(target).startswith(str(project_root)) else target
        return "verified", [str(rel)], 0.99, f"file exists at {rel}"
    matches = list(project_root.rglob(Path(claim).name))[:3]
    if matches:
        rels = [str(m.relative_to(project_root)) for m in matches]
        return (
            "unknown",
            rels,
            0.55,
            f"basename {Path(claim).name!r} matches elsewhere; literal path {claim!r} not found",
        )
    return "refuted", [], 0.95, f"no file at {claim} and no basename match in repo"


def verify_function(claim, project_root: Path):
    pattern = re.compile(
        rf"\b(?:function\s+{re.escape(claim)}\b"
        rf"|const\s+{re.escape(claim)}\s*="
        rf"|let\s+{re.escape(claim)}\s*="
        rf"|def\s+{re.escape(claim)}\b"
        rf"|class\s+{re.escape(claim)}\b"
        rf"|export\s+(?:default\s+)?(?:function\s+|const\s+|class\s+)?{re.escape(claim)}\b"
        rf"|{re.escape(claim)}\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"
        rf")"
    )
    evidence = []
    for ext in (".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs", ".py"):
        for f in project_root.rglob(f"*{ext}"):
            parts = set(f.parts)
            if parts & {"node_modules", ".git", "dist", "build", ".venv", ".venv-gpu"}:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    evidence.append(f"{f.relative_to(project_root)}:{line_no}")
                    if len(evidence) >= 5:
                        break
            if len(evidence) >= 5:
                break
        if len(evidence) >= 5:
            break
    if evidence:
        return "verified", evidence, 0.85, f"{len(evidence)} definition(s) found"
    return "refuted", [], 0.7, f"no definition of {claim}() found in source"


def verify_command(claim, project_root: Path):
    pkg = project_root / "package.json"
    if not pkg.exists():
        return "unknown", [], 0.4, "no package.json at project root"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown", [], 0.3, "package.json unreadable"
    scripts = data.get("scripts", {})
    if claim in scripts:
        return "verified", [f"package.json#scripts.{claim}"], 0.99, f"script {claim!r} present"
    return "refuted", [], 0.95, f"script {claim!r} not in package.json"


def verify_dependency(claim, project_root: Path):
    pkg = project_root / "package.json"
    py_pkg = project_root / "pyproject.toml"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "unknown", [], 0.3, "package.json unreadable"
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            if claim in data.get(key, {}):
                return "verified", [f"package.json#{key}.{claim}"], 0.99, f"{claim} in {key}"
        return "refuted", [], 0.9, f"{claim} not in package.json deps"
    if py_pkg.exists():
        try:
            content = py_pkg.read_text(encoding="utf-8")
        except OSError:
            return "unknown", [], 0.3, "pyproject.toml unreadable"
        if claim in content:
            return "verified", ["pyproject.toml"], 0.8, f"{claim} mentioned in pyproject.toml"
        return "refuted", [], 0.85, f"{claim} not in pyproject.toml"
    return "unknown", [], 0.4, "no package.json or pyproject.toml"


VERIFIERS = {
    "file_path": verify_file_path,
    "function": verify_function,
    "command": verify_command,
    "dependency": verify_dependency,
}


def make_pair(doc_path: Path, project_root: Path, line_no, category, claim, project_id):
    verifier = VERIFIERS[category]
    status, evidence, confidence, reason = verifier(claim, project_root)
    output = {
        "claim": claim,
        "status": status,
        "evidence": evidence,
        "confidence": confidence,
        "reason": reason,
    }
    # Redact the doc rel path is fine; redact the claim itself in case it
    # accidentally contains a token-shaped string.
    redacted_claim, redacted = redact(claim)
    rel_doc = doc_path.relative_to(project_root) if str(doc_path).startswith(str(project_root)) else doc_path
    input_payload = {
        "doc_path": str(rel_doc),
        "project_root": str(project_root),
        "claim": redacted_claim,
        "claim_category": category,
        "line": line_no,
    }
    return {
        "schema_version": "slm-learning-doc-verifier-pair@1",
        "input": input_payload,
        "output": output,
        "provenance": {
            "source_file": str(rel_doc),
            "agent_type": "gad-doc-verifier",
            "input_context_hash": hash_text(json.dumps(input_payload, sort_keys=True)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "human_approved": False,
            "later_contradicted": False,
            "secret_redacted": redacted,
            "data_tier": "bootstrapped",
        },
    }


def project_id_for_root(root: Path):
    return root.name.replace("_", "-")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[], help="Project root (repeatable).")
    parser.add_argument("--out", required=True, help="Output JSONL path.")
    parser.add_argument("--max-claims-per-doc", type=int, default=20)
    parser.add_argument("--max-docs-per-root", type=int, default=200)
    parser.add_argument("--json", action="store_true", help="Print summary JSON to stdout.")
    args = parser.parse_args()

    roots = [Path(r).resolve() for r in (args.root or ["."])]
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {
        "verified": 0,
        "refuted": 0,
        "unknown": 0,
        "by_category": {"file_path": 0, "function": 0, "command": 0, "dependency": 0},
        "by_root": {},
        "total": 0,
    }
    with out_path.open("w", encoding="utf-8") as f:
        for root in roots:
            project_id = project_id_for_root(root)
            root_count = 0
            doc_count = 0
            for doc in find_markdown_files(root):
                if doc_count >= args.max_docs_per_root:
                    break
                doc_count += 1
                claims = extract_claims_from_doc(doc, root)
                claims = claims[: args.max_claims_per_doc]
                for line_no, category, claim in claims:
                    pair = make_pair(doc, root, line_no, category, claim, project_id)
                    f.write(json.dumps(pair, separators=(",", ":")) + "\n")
                    counts[pair["output"]["status"]] += 1
                    counts["by_category"][category] += 1
                    counts["total"] += 1
                    root_count += 1
            counts["by_root"][project_id] = root_count

    payload = {
        "schema_version": "slm-learning-doc-verifier-pair@1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out": str(out_path),
        "roots": [str(r) for r in roots],
        "counts": counts,
    }
    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"bootstrapped doc-verifier pairs: {counts['total']} -> {out_path}")
        print(f"  verified: {counts['verified']} | refuted: {counts['refuted']} | unknown: {counts['unknown']}")
        print(f"  by_category: {counts['by_category']}")
        print(f"  by_root    : {counts['by_root']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
