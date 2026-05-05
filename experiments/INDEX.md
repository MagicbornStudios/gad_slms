# Experiment Index

| run | started | stage | epochs | lr | max_pairs | final_loss | elapsed | gad_tools_passed | notes |
|-----|---------|-------|--------|----|-----------|-----------|---------|------------------|-------|
| dr_stein_baseline EVAL | 2026-05-05T00:56:31 |  |  |  |  |  |  | 0/30 (0.0%) |  |
| baseline_repro | 2026-05-05T00:48:33 | reasoning | 5 | 1e-05 | 100 | 4.1438 | 485.6s |  | Sanity-check reproduction of Phase 02 defaults. [salvaged manifest after runner UTF-8 crash] |
| baseline_repro EVAL | 2026-05-05T01:03:49 |  |  |  |  |  |  | 0/30 (0.0%) |  |
| higher_lr | 2026-05-05T00:57:16 | reasoning | 5 | 5e-05 | 100 | 1.4744 | 502.6s |  | Higher LR — trade preservation for faster convergence. [salvaged manifest after runner UTF-8 crash] |
| higher_lr EVAL | 2026-05-05T01:09:28 |  |  |  |  |  |  | 1/30 (3.3%) |  |
| lower_lr_longer | 2026-05-05T01:05:40 | reasoning | 10 | 5e-06 | 100 | 3.9734 | 852.7s | Lower LR + 2x epochs to preserve SFT knowledge. |
| lower_lr_longer EVAL | 2026-05-05T01:25:26 |  |  |  |  |  |  | 1/30 (3.3%) |  |
| more_epochs | 2026-05-05T01:20:30 | reasoning | 10 | 1e-05 | 100 | 2.802 | 889.6s | Test whether 10 epochs (vs 5) keeps avg_loss decreasing. |
| more_epochs EVAL | 2026-05-05T01:39:20 |  |  |  |  |  |  | 0/30 (0.0%) |  |
| more_pairs | 2026-05-05T01:35:58 | reasoning | 5 | 1e-05 | 200 | 2.8631 | 1745.6s | Test whether 200 pairs (vs 100) improves alignment without overfitting. |
