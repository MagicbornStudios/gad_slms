# slm-learning Colab notebooks

## `train_colab.ipynb`

Master training notebook. Pulls the repo into a fresh Colab session, installs deps, auths to HF Hub, then runs `scripts/sweep_finetune.py` against every config in `experiments/configs/colab/`. Each config trains, runs the eval matrix (gad_tools + humaneval + gsm8k), and pushes the adapter to `scrubster/dr-stein-<config-name>`.

### One-time setup

1. Open the notebook in Colab via:
   `https://colab.research.google.com/github/MagicbornStudios/gad_slms/blob/master/notebooks/train_colab.ipynb`
2. **Runtime → Change runtime type → A100 GPU** (Colab Pro biases here).
3. **Add secret** `HF_TOKEN` (left sidebar key icon) with a HF *write* token from huggingface.co/settings/tokens. Toggle "Notebook access" on.

### Each session

Open the notebook → Runtime → Run all. Walk away. ~25-35 min on A100 for 3 configs.

### Adding a new experiment

Drop a YAML in `experiments/configs/colab/` (commit + push), open the notebook, hit Run all. The sweep skips configs whose MANIFEST already exists, so existing runs aren't re-trained.

To re-train an existing config (different LR, fresh seed), edit cell 6 to add `--rerun`.

### What gets shipped

- Adapter dir → `scrubster/dr-stein-<config-name>` on HF Hub (public)
- MANIFEST.json + eval JSONs → `experiments/runs/<name>/` in the Colab session (gone when runtime resets, but the canonical artifacts are on Hub)

### Local follow-up

Once a Colab run finishes, you can pull the adapter locally:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "Qwen/Qwen2.5-1.5B-Instruct"  # match the config's base_model
adapter = "scrubster/dr-stein-colab_qwen15_math_5k"

model = AutoModelForCausalLM.from_pretrained(base, dtype="bfloat16", device_map="auto")
model = PeftModel.from_pretrained(model, adapter)
tok = AutoTokenizer.from_pretrained(adapter)
```

### Why notebooks not a launcher script

We have a stub at `scripts/remote/colab_launcher.py` (decision `slm-learning-020`) but a manually-opened notebook is the simplest interface for the operator-triggered cadence we're using right now. If we move to scheduled / unattended Colab runs (e.g. via the Colab API or a cron-like dispatcher), revisit the launcher.
