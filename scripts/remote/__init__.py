"""Remote-compute launchers (decision slm-learning-020).

When a FinetuneConfig.compute_target is one of `colab-*`, `kaggle-*`,
or `hf-*`, the sweep runner dispatches here instead of running a
local subprocess.

Each launcher takes a FinetuneConfig and returns a Path to the
retrieved checkpoint + manifest, written into experiments/runs/<name>/
as if the run had been local. Implementations are stubs until the
local pipeline is stable enough to be worth pushing to a remote box.
"""
