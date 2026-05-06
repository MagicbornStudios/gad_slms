"""Continuous Local Delta Lab subprocess interface.

Per slm-learning-051: continuous training creates CANDIDATES, not
auto-merged adapters. These scripts implement the subprocess contract
the global daemon (gad-monorepo phase 147) calls into.

  train_lora_delta.py  — produce a candidate adapter from a manifest
  eval_candidate.py    — score the candidate against the benchmark battery
  promote_atomic.py    — REFUSED by default; manual promotion only

The daemon should never bypass promote_atomic.py's gate.
"""
