"""Pluggable design JSON -> framework-specific code generators.

Per slm-learning-205. Stubs for v1: each generator emits a theme file,
one file per component, one file per page, and a MANIFEST.json. Real
code generation (calls to Claude API or MCP) is deferred. The pattern
under test here is the plug-in registry + manifest contract.

To add a new framework target: subclass CodeGenerator, implement
generate(), and register the instance in ``generators``.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any


# -----------------------------------------------------------------------------
# Result type
# -----------------------------------------------------------------------------
@dataclass
class GenerationResult:
    target_framework: str
    out_dir: str
    files_written: list[str] = field(default_factory=list)
    manifest_path: str = ""
    notes: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _pascal(name: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", name or "")
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def _kebab(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name or "")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s)
    return s.strip("-").lower()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write(path: str, content: str) -> str:
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _write_manifest(out_dir: str, payload: dict[str, Any]) -> str:
    path = os.path.join(out_dir, "MANIFEST.json")
    _ensure_dir(out_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


# -----------------------------------------------------------------------------
# Base class
# -----------------------------------------------------------------------------
class CodeGenerator:
    target_framework: str = ""
    component_ext: str = ""
    theme_filename: str = ""

    def generate(
        self, bundle: dict[str, Any], target_framework: str, out_dir: str
    ) -> GenerationResult:
        raise NotImplementedError

    # -- shared manifest builder -----------------------------------------------
    def _build_manifest(
        self,
        bundle: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prov = bundle.get("provenance", {}) or {}
        return {
            "bundle_id": bundle.get("bundle_id"),
            "design_system_version": bundle.get("design_system_version"),
            "target_framework": self.target_framework,
            "tenant_id": prov.get("tenant_id"),
            "consent": prov.get("consent", {}),
            "decision_refs": bundle.get(
                "decision_refs",
                ["slm-learning-205", "slm-learning-219", "slm-learning-221"],
            ),
            "files": files,
        }


# -----------------------------------------------------------------------------
# React generator
# -----------------------------------------------------------------------------
class ReactGenerator(CodeGenerator):
    target_framework = "react"
    component_ext = "jsx"
    theme_filename = "theme.css"

    def _emit_theme(self, tokens: dict[str, Any], out_dir: str) -> str:
        lines = [":root {"]
        for cname, cval in (tokens.get("color") or {}).items():
            lines.append(f"  --color-{_kebab(cname)}: {cval};")
        for sname, sval in (tokens.get("spacing") or {}).items():
            lines.append(f"  --space-{_kebab(sname)}: {sval};")
        for rname, rval in (tokens.get("radius") or {}).items():
            lines.append(f"  --radius-{_kebab(rname)}: {rval};")
        for shname, shval in (tokens.get("shadow") or {}).items():
            lines.append(f"  --shadow-{_kebab(shname)}: {shval};")
        for tname, tval in (tokens.get("typography") or {}).items():
            if isinstance(tval, dict):
                if tval.get("font_family"):
                    lines.append(f"  --font-{_kebab(tname)}-family: {tval['font_family']};")
                if tval.get("size"):
                    lines.append(f"  --font-{_kebab(tname)}-size: {tval['size']};")
                if tval.get("weight") is not None:
                    lines.append(f"  --font-{_kebab(tname)}-weight: {tval['weight']};")
        lines.append("}")
        path = os.path.join(out_dir, self.theme_filename)
        return _write(path, "\n".join(lines) + "\n")

    def _emit_component(self, comp: dict[str, Any], out_dir: str) -> str:
        name = _pascal(comp.get("name") or comp.get("component_id") or "Component")
        comp_id = comp.get("component_id", "")
        category = comp.get("category", "display")
        body = (
            f"// Generated from component_id: {comp_id}\n"
            f"// Category: {category}\n"
            f"// TODO(claude-design-generator): implement structure from bundle.components[].structure\n"
            f"export function {name}(props) {{\n"
            f"  return null;\n"
            f"}}\n"
        )
        path = os.path.join(out_dir, "components", f"{name}.{self.component_ext}")
        return _write(path, body)

    def _emit_page(self, page: dict[str, Any], out_dir: str) -> str:
        name = _pascal(page.get("page_id") or "Page")
        used = page.get("components_used") or []
        imports = "\n".join(
            f"import {{ {_pascal(u.get('component_id'))} }} from '../components/{_pascal(u.get('component_id'))}';"
            for u in used
            if u.get("component_id")
        )
        body = (
            f"// Generated from page_id: {page.get('page_id')}\n"
            f"// Route: {page.get('route')}\n"
            f"// Layout: {page.get('layout')}\n"
            f"// TODO(claude-design-generator): wire layout + slots\n"
            f"{imports}\n\n"
            f"export default function {name}() {{\n"
            f"  return null;\n"
            f"}}\n"
        )
        path = os.path.join(out_dir, "pages", f"{name}.{self.component_ext}")
        return _write(path, body)

    def generate(self, bundle, target_framework, out_dir):
        _ensure_dir(out_dir)
        files: list[dict[str, Any]] = []
        theme_path = self._emit_theme(bundle.get("tokens", {}) or {}, out_dir)
        files.append({"kind": "theme", "path": theme_path})
        for comp in bundle.get("components", []) or []:
            p = self._emit_component(comp, out_dir)
            files.append({"kind": "component", "component_id": comp.get("component_id"), "path": p})
        for page in bundle.get("pages", []) or []:
            p = self._emit_page(page, out_dir)
            files.append({"kind": "page", "page_id": page.get("page_id"), "path": p})
        manifest = self._build_manifest(bundle, files)
        manifest_path = _write_manifest(out_dir, manifest)
        return GenerationResult(
            target_framework=self.target_framework,
            out_dir=out_dir,
            files_written=[f["path"] for f in files] + [manifest_path],
            manifest_path=manifest_path,
        )


# -----------------------------------------------------------------------------
# Flutter generator
# -----------------------------------------------------------------------------
class FlutterGenerator(CodeGenerator):
    target_framework = "flutter"
    component_ext = "dart"
    theme_filename = "theme.dart"

    def _emit_theme(self, tokens, out_dir):
        lines = [
            "// TODO(claude-design-generator): emit ThemeData from tokens",
            "import 'package:flutter/material.dart';",
            "",
            "class AppTheme {",
            "  static ThemeData build() {",
            "    return ThemeData(",
            "      // colors / typography / spacing tokens map here",
            "    );",
            "  }",
            "}",
            "",
        ]
        path = os.path.join(out_dir, self.theme_filename)
        return _write(path, "\n".join(lines))

    def _emit_component(self, comp, out_dir):
        name = _pascal(comp.get("name") or comp.get("component_id") or "Component")
        body = (
            f"// Generated from component_id: {comp.get('component_id', '')}\n"
            f"// TODO(claude-design-generator): implement widget tree\n"
            f"import 'package:flutter/material.dart';\n\n"
            f"class {name} extends StatelessWidget {{\n"
            f"  const {name}({{super.key}});\n\n"
            f"  @override\n"
            f"  Widget build(BuildContext context) => const SizedBox.shrink();\n"
            f"}}\n"
        )
        path = os.path.join(out_dir, "widgets", f"{_kebab(name)}.{self.component_ext}")
        return _write(path, body)

    def _emit_page(self, page, out_dir):
        name = _pascal(page.get("page_id") or "Page")
        body = (
            f"// Generated from page_id: {page.get('page_id')}\n"
            f"// Route: {page.get('route')}\n"
            f"// TODO(claude-design-generator): wire layout + slots\n"
            f"import 'package:flutter/material.dart';\n\n"
            f"class {name}Page extends StatelessWidget {{\n"
            f"  const {name}Page({{super.key}});\n\n"
            f"  @override\n"
            f"  Widget build(BuildContext context) => const Scaffold();\n"
            f"}}\n"
        )
        path = os.path.join(out_dir, "pages", f"{_kebab(name)}.{self.component_ext}")
        return _write(path, body)

    def generate(self, bundle, target_framework, out_dir):
        _ensure_dir(out_dir)
        files = [{"kind": "theme", "path": self._emit_theme(bundle.get("tokens", {}) or {}, out_dir)}]
        for comp in bundle.get("components", []) or []:
            p = self._emit_component(comp, out_dir)
            files.append({"kind": "component", "component_id": comp.get("component_id"), "path": p})
        for page in bundle.get("pages", []) or []:
            p = self._emit_page(page, out_dir)
            files.append({"kind": "page", "page_id": page.get("page_id"), "path": p})
        manifest_path = _write_manifest(out_dir, self._build_manifest(bundle, files))
        return GenerationResult(
            target_framework=self.target_framework,
            out_dir=out_dir,
            files_written=[f["path"] for f in files] + [manifest_path],
            manifest_path=manifest_path,
        )


# -----------------------------------------------------------------------------
# HTML+CSS generator
# -----------------------------------------------------------------------------
class HtmlCssGenerator(CodeGenerator):
    target_framework = "html-css"
    component_ext = "html"
    theme_filename = "theme.css"

    def _emit_theme(self, tokens, out_dir):
        # Reuse React's CSS-vars approach.
        return ReactGenerator()._emit_theme(tokens, out_dir)

    def _emit_component(self, comp, out_dir):
        name = _pascal(comp.get("name") or comp.get("component_id") or "Component")
        body = (
            f"<!-- Generated from component_id: {comp.get('component_id', '')} -->\n"
            f"<!-- TODO(claude-design-generator): implement structure -->\n"
            f"<template id=\"{_kebab(name)}\"></template>\n"
        )
        path = os.path.join(out_dir, "components", f"{_kebab(name)}.{self.component_ext}")
        return _write(path, body)

    def _emit_page(self, page, out_dir):
        name = _pascal(page.get("page_id") or "Page")
        body = (
            f"<!-- Generated from page_id: {page.get('page_id')} -->\n"
            f"<!-- Route: {page.get('route')} -->\n"
            f"<!-- TODO(claude-design-generator): wire layout + slots -->\n"
            f"<!doctype html><html><head><title>{page.get('title', name)}</title>"
            f"<link rel=\"stylesheet\" href=\"../{self.theme_filename}\"></head><body></body></html>\n"
        )
        path = os.path.join(out_dir, "pages", f"{_kebab(name)}.{self.component_ext}")
        return _write(path, body)

    def generate(self, bundle, target_framework, out_dir):
        _ensure_dir(out_dir)
        files = [{"kind": "theme", "path": self._emit_theme(bundle.get("tokens", {}) or {}, out_dir)}]
        for comp in bundle.get("components", []) or []:
            p = self._emit_component(comp, out_dir)
            files.append({"kind": "component", "component_id": comp.get("component_id"), "path": p})
        for page in bundle.get("pages", []) or []:
            p = self._emit_page(page, out_dir)
            files.append({"kind": "page", "page_id": page.get("page_id"), "path": p})
        manifest_path = _write_manifest(out_dir, self._build_manifest(bundle, files))
        return GenerationResult(
            target_framework=self.target_framework,
            out_dir=out_dir,
            files_written=[f["path"] for f in files] + [manifest_path],
            manifest_path=manifest_path,
        )


# -----------------------------------------------------------------------------
# Plug-in registry
# -----------------------------------------------------------------------------
generators: dict[str, CodeGenerator] = {
    "react": ReactGenerator(),
    "flutter": FlutterGenerator(),
    "html-css": HtmlCssGenerator(),
}


def get_generator(target_framework: str) -> CodeGenerator:
    if target_framework not in generators:
        raise ValueError(
            f"Unknown target_framework {target_framework!r}. "
            f"Registered: {sorted(generators)}"
        )
    return generators[target_framework]


__all__ = [
    "CodeGenerator",
    "GenerationResult",
    "ReactGenerator",
    "FlutterGenerator",
    "HtmlCssGenerator",
    "generators",
    "get_generator",
]
