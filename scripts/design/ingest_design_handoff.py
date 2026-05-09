"""Ingest a Claude Design handoff bundle and dispatch to a code generator.

Per slm-learning-205. v1 implements the FILE INGEST path. The webhook
path (Option A in the architecture doc) is documented but deferred
until the GAD Gateway HTTP server is in place.

API:
    ingest(bundle_path, *, validate=True) -> IngestResult

CLI:
    python scripts/design/ingest_design_handoff.py <bundle.json> --validate-only
    python scripts/design/ingest_design_handoff.py <bundle.json> \\
        --target-framework react --out src/generated/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

# Make sibling import work whether invoked as a script or a module.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from design_to_code import get_generator, generators  # noqa: E402


SCHEMA_PATH = os.path.normpath(
    os.path.join(_THIS_DIR, "..", "..", "schemas", "design_handoff_bundle.schema.json")
)


@dataclass
class IngestResult:
    bundle_id: str
    n_pages: int
    n_components: int
    n_tokens: int
    validation_errors: list[str] = field(default_factory=list)
    dispatched_to: str = ""
    output_paths: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
_REQUIRED_TOP = [
    "bundle_id",
    "exported_at",
    "design_system_version",
    "tokens",
    "pages",
    "components",
    "provenance",
]


def _manual_validate(bundle: dict[str, Any]) -> list[str]:
    """Fallback validator when ``jsonschema`` is unavailable."""
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle is not a JSON object"]
    for key in _REQUIRED_TOP:
        if key not in bundle:
            errors.append(f"missing required top-level field: {key}")

    tokens = bundle.get("tokens")
    if tokens is not None and not isinstance(tokens, dict):
        errors.append("tokens must be an object")

    pages = bundle.get("pages")
    if pages is not None:
        if not isinstance(pages, list):
            errors.append("pages must be an array")
        else:
            for i, p in enumerate(pages):
                if not isinstance(p, dict):
                    errors.append(f"pages[{i}] is not an object")
                    continue
                for k in ("page_id", "route", "layout", "components_used"):
                    if k not in p:
                        errors.append(f"pages[{i}] missing {k}")

    comps = bundle.get("components")
    if comps is not None:
        if not isinstance(comps, list):
            errors.append("components must be an array")
        else:
            for i, c in enumerate(comps):
                if not isinstance(c, dict):
                    errors.append(f"components[{i}] is not an object")
                    continue
                for k in ("component_id", "name", "category", "props_schema", "structure"):
                    if k not in c:
                        errors.append(f"components[{i}] missing {k}")

    prov = bundle.get("provenance")
    if prov is not None:
        if not isinstance(prov, dict):
            errors.append("provenance must be an object")
        else:
            for k in ("source", "exported_from"):
                if k not in prov:
                    errors.append(f"provenance missing {k}")

    return errors


def _validate(bundle: dict[str, Any]) -> list[str]:
    """Validate against the JSON schema, falling back to manual checks."""
    try:
        import jsonschema  # type: ignore
    except Exception:
        return _manual_validate(bundle)

    if not os.path.exists(SCHEMA_PATH):
        return _manual_validate(bundle) + [f"schema file not found at {SCHEMA_PATH}"]

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    validator_cls = getattr(jsonschema, "Draft202012Validator", None)
    if validator_cls is None:
        validator_cls = jsonschema.Draft7Validator  # type: ignore[attr-defined]

    validator = validator_cls(schema)
    errs: list[str] = []
    for err in validator.iter_errors(bundle):
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errs.append(f"{path}: {err.message}")
    return errs


# -----------------------------------------------------------------------------
# Token counter
# -----------------------------------------------------------------------------
def _count_tokens(tokens: dict[str, Any]) -> int:
    n = 0
    for group in (tokens or {}).values():
        if isinstance(group, dict):
            n += len(group)
    return n


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def ingest(
    bundle_path: str,
    *,
    validate: bool = True,
    target_framework: str | None = None,
    out_dir: str | None = None,
) -> IngestResult:
    """Read a bundle, validate it, optionally dispatch to a generator."""
    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    errs = _validate(bundle) if validate else []

    result = IngestResult(
        bundle_id=str(bundle.get("bundle_id", "")),
        n_pages=len(bundle.get("pages") or []),
        n_components=len(bundle.get("components") or []),
        n_tokens=_count_tokens(bundle.get("tokens") or {}),
        validation_errors=errs,
        provenance=bundle.get("provenance", {}) or {},
    )

    if errs and validate:
        # Refuse to dispatch on a bundle that didn't pass validation.
        return result

    if target_framework and out_dir:
        gen = get_generator(target_framework)
        gen_result = gen.generate(bundle, target_framework, out_dir)
        result.dispatched_to = target_framework
        result.output_paths = list(gen_result.files_written)

    return result


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ingest a Claude Design handoff bundle (slm-learning-205).",
    )
    p.add_argument("bundle_path", help="Path to bundle.json")
    p.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the bundle and exit without generating code.",
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip schema validation (NOT recommended; v1 default is to validate).",
    )
    p.add_argument(
        "--target-framework",
        choices=sorted(generators.keys()),
        help="Framework target for code generation.",
    )
    p.add_argument(
        "--out",
        help="Output directory for generated code.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print the IngestResult as JSON.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    if args.validate_only:
        result = ingest(args.bundle_path, validate=True)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"bundle_id: {result.bundle_id}")
            print(f"pages: {result.n_pages}  components: {result.n_components}  tokens: {result.n_tokens}")
            if result.validation_errors:
                print(f"validation_errors ({len(result.validation_errors)}):")
                for e in result.validation_errors:
                    print(f"  - {e}")
            else:
                print("validation_errors: none")
        return 0 if not result.validation_errors else 1

    if not args.target_framework or not args.out:
        print("error: --target-framework and --out are required unless --validate-only", file=sys.stderr)
        return 2

    result = ingest(
        args.bundle_path,
        validate=(not args.no_validate),
        target_framework=args.target_framework,
        out_dir=args.out,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"bundle_id: {result.bundle_id}")
        print(f"dispatched_to: {result.dispatched_to or '(none)'}")
        print(f"pages: {result.n_pages}  components: {result.n_components}  tokens: {result.n_tokens}")
        if result.validation_errors:
            print(f"validation_errors ({len(result.validation_errors)}):")
            for e in result.validation_errors:
                print(f"  - {e}")
        print(f"output_paths: {len(result.output_paths)} files")
        for p in result.output_paths:
            print(f"  - {p}")

    return 0 if not result.validation_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
