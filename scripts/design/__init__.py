"""Claude Design -> GAD generation engine pipeline.

Per slm-learning-205, Claude Design handoff JSON bundles are first-class
trigger payloads for the GAD generation engine. This package implements
the v1 file-ingest path:

  ingest_design_handoff.py  read + validate a bundle, dispatch to a generator
  design_to_code.py         pluggable framework-target code generators

Webhook + CI/CD modes are documented in
``reports/research/claude_design_pipeline.md`` and deferred to later
iterations.
"""
