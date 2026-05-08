# news/

Weekly intake folder for AI/SLM/LLM news that's relevant to slm-learning's
research program. The fetch script is `scripts/registry/fetch_news.py`;
files land here as dated Markdown digests so they show up in `gad snapshot`
and the planning site.

## Cadence

- Manual or scheduled (e.g. `gad cron weekly --command "python scripts/registry/fetch_news.py"`)
- Each run produces `news/YYYY-MM-DD-digest.md` with sections per source.

## Sources tracked

| Source | URL | Why |
|---|---|---|
| Anthropic blog | https://www.anthropic.com/news | Opus/Sonnet/Haiku release, pricing, new features. Affects `claude-*` rows in `data/registry/teachers.json`. |
| HF papers | https://huggingface.co/papers | New SLM training papers, distillation, RLEF, RLVR, MoE work. |
| Qwen releases | https://huggingface.co/Qwen | Backbone updates (2.5 → 3.x → Next). Affects every Charter Row. |
| OpenAI blog | https://openai.com/news | gpt-oss releases, frontier moves. |
| DeepSeek releases | https://huggingface.co/deepseek-ai | R1 family + V3 + math specialists. |
| EvalPlus | https://github.com/evalplus/evalplus | HumanEval+ / MBPP+ versions; eval methodology drift. |
| LiveCodeBench | https://livecodebench.github.io | Eval refresh schedule; leakage notes. |
| OpenRouter free tier | https://openrouter.ai/models | Free comparator availability. |

## What goes here vs. what doesn't

YES:
- New model releases that change `teachers.json` or `model_families.json` rows
- New datasets that change `datasets.json`
- Major eval refreshes (LiveCodeBench monthly cuts, HumanEval+ updates)
- Pricing changes that affect Two-Shot $50 budgeting
- Methodology papers that propose techniques we should consider

NO:
- General AI news without a dataset / model / eval impact
- Marketing announcements without a verifiable model card / paper
- Speculation without dates or arXiv ids

## Promotion path

A digest entry that warrants action gets promoted to:

1. A registry update (`data/registry/{datasets,model_families,teachers}.json`)
2. A decision (`gad decisions add slm-learning-NNN ...`)
3. A note (`gad note add ...`) for tracking experiments triggered by it

Decision refs: slm-learning-198.
