"""Distillation + synthetic augmentation utilities.

Per slm-learning-019, distillation pairs are produced via Claude Code
subagent dispatch (Agent tool). Per slm-learning-091, deterministic
augmentation (e.g. fake-parent-prefix synthesis) is the cheap-first
move when the data shape is structural rather than semantic.
"""
