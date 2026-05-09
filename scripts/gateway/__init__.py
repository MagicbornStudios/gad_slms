"""GAD Gateway — task_shape -> model routing + JSONL trace logging.

Decision refs: slm-learning-208 (Gateway scaffold), slm-learning-197
(teacher policy), slm-learning-103 (compare-and-compete discipline).

This package is distinct from the legacy `scripts/gateway/route.py`
(intent/risk router, slm-learning-085). The new modules in this
package route by `task_shape` against `routes.json` seeded from the
teacher registry and log every call to JSONL for cost rollup.
"""

__version__ = "0.1.0"
