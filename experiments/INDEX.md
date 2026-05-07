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
| baseline_repro EVAL | 2026-05-05T08:55:42 |  |  |  |  |  |  | 0/30 (0.0%) | re-eval temp=0.0 device=cuda; previous 0/30 confirmed |
| higher_lr EVAL | 2026-05-05T08:56:20 |  |  |  |  |  |  | 0/30 (0.0%) | re-eval temp=0.0 device=cuda; previous 1/30 was sampling noise |
| lower_lr_longer EVAL | 2026-05-05T08:57:08 |  |  |  |  |  |  | 0/30 (0.0%) | re-eval temp=0.0 device=cuda; previous 1/30 was sampling noise |
| more_epochs EVAL | 2026-05-05T08:58:02 |  |  |  |  |  |  | 0/30 (0.0%) | re-eval temp=0.0 device=cuda; previous 0/30 confirmed |
| more_pairs EVAL | 2026-05-05T08:58:48 |  |  |  |  |  |  | 0/30 (0.0%) | first eval (was killed yesterday at 2/30 progress); temp=0.0 device=cuda, 46.5s |
| dr_stein_baseline_temp0 EVAL | 2026-05-05T08:59:54 |  |  |  |  |  |  | 0/30 (0.0%) | re-eval of dr_stein.pt temp=0.0 device=cuda; previous 0/30 confirmed |
| sft_model EVAL (humaneval) | 2026-05-05T09:59:58 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| sft_model EVAL (gsm8k) | 2026-05-05T10:18:02 |  |  |  |  |  |  | 0/50 (0.0%) | n=50 temp=0.0 device=auto |
| reasoning_model EVAL (humaneval) | 2026-05-05T10:18:02 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| reasoning_model EVAL (gsm8k) | 2026-05-05T10:18:02 |  |  |  |  |  |  | 0/50 (0.0%) | n=50 temp=0.0 device=auto |
| dr_stein EVAL (humaneval) | 2026-05-05T10:18:02 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| dr_stein EVAL (gsm8k) | 2026-05-05T10:18:02 |  |  |  |  |  |  | 0/50 (0.0%) | n=50 temp=0.0 device=auto |
| baseline_repro EVAL (humaneval) | 2026-05-05T10:20:29 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| baseline_repro EVAL (gsm8k) | 2026-05-05T10:22:50 |  |  |  |  |  |  | 0/50 (0.0%) | n=50 temp=0.0 device=auto |
| higher_lr EVAL (humaneval) | 2026-05-05T10:23:54 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| higher_lr EVAL (gsm8k) | 2026-05-05T10:26:43 |  |  |  |  |  |  | 0/50 (0.0%) | n=50 temp=0.0 device=auto |
| lower_lr_longer EVAL (humaneval) | 2026-05-05T10:29:14 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| lower_lr_longer EVAL (gsm8k) | 2026-05-05T10:31:41 |  |  |  |  |  |  | 1/50 (2.0%) | n=50 temp=0.0 device=auto |
| more_epochs EVAL (humaneval) | 2026-05-05T10:33:39 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| more_epochs EVAL (gsm8k) | 2026-05-05T10:34:55 |  |  |  |  |  |  | 1/50 (2.0%) | n=50 temp=0.0 device=auto |
| more_pairs EVAL (humaneval) | 2026-05-05T10:37:06 |  |  |  |  |  |  | 0/10 (0.0%) | n=10 temp=0.0 device=auto |
| more_pairs EVAL (gsm8k) | 2026-05-05T10:40:20 |  |  |  |  |  |  | 1/50 (2.0%) | n=50 temp=0.0 device=auto |
| stage25_gad_tools_lora EVAL | 2026-05-05T12:01:39 |  |  |  |  |  |  | 9/30 (30.0%) |  |
| stage25_gad_tools_lora_higher_lr EVAL | 2026-05-05T12:17:54 |  |  |  |  |  |  | 12/30 (40.0%) |  |
| stage25_qwen15_instruct_control EVAL | 2026-05-05T15:29:33 |  |  |  |  |  |  | 22/30 (73.3%) |  |
| stage25_qwen15_distill_reasoning EVAL | 2026-05-05T15:56:41 |  |  |  |  |  |  | 8/30 (26.7%) |  |
| stage25_qwen15_instruct_control_bf16 EVAL | 2026-05-05T16:50:17 |  |  |  |  |  |  | 22/30 (73.3%) |  |
| stage25_qwen15_instruct_v2 EVAL | 2026-05-05T18:37:45 |  |  |  |  |  |  | 30/30 (100.0%) |  |
| stage25_qwen15_multitask EVAL | 2026-05-06T12:59:29 |  |  |  |  |  |  | 25/30 (83.3%) |  |
| stage25_qwen15_doc_verifier_r8 EVAL | 2026-05-06T14:22:38 |  |  |  |  |  |  | 11/30 (36.7%) |  |
| stage25_qwen15_doc_verifier_r16 EVAL | 2026-05-06T15:07:19 |  |  |  |  |  |  | 10/30 (33.3%) |  |
