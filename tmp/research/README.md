# Research Intake

Per `slm-learning-106`. External research code/papers/blogs land here.

## Structure

```
tmp/research/
├── papers/        — PDF or markdown summaries of papers
├── repos/         — git clones of external repos under review
├── experiments/   — local experiments derived from the research
├── reviews/       — research review records (one JSON per pull)
└── README.md      — this file
```

## Per-pull manifest

Every pull MUST create a record at `tmp/research/reviews/<research_id>.json`:

```json
{
  "research_id": "sera-2026-01",
  "source": "paper",
  "url": "https://huggingface.co/papers/2601.20789",
  "cloned_to": "tmp/research/repos/sera",
  "review_status": "unreviewed",
  "ideas_extracted": [],
  "risks": [],
  "license": "Apache 2.0",
  "gad_relevance": "high",
  "next_test": "implement soft-verification trajectory generator",
  "ts_pulled": "2026-05-08T..."
}
```

Statuses:
- `unreviewed` — just pulled
- `reviewed` — read + ideas extracted
- `promoted` — useful idea moved into production code with provenance
- `rejected` — not useful for our path
- `skeleton` — preserve as fossil/museum entry; not promoted

## Rules (per `slm-learning-106`)

1. Never pollute production code from `tmp/research/`. Promote ideas
   ONLY by writing fresh code in `scripts/` / `src/` with explicit
   reference to the research_id.
2. Every cloned repo gets a research review.
3. Useful ideas become genes/deltas/tasks (with EXP-id).
4. Unused but interesting code becomes a skeleton/museum entry under
   `.planning/skeletons/`.
5. No dependency adopted without license/security review.
6. Every research claim needs a benchmark or reproduction path.

## .gitignore

The `papers/` and `repos/` subdirs are gitignored — they may contain
large clones. The `reviews/` and `experiments/` subdirs ARE tracked
because the review records and our derived experiments are valuable
provenance.
