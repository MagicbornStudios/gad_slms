# Multi-GPU + remote training enabling work

Once eGPU is detected: (1) torch DDP for two-GPU local training (each 1660 Ti = 6GB, total 12GB usable), (2) DeepSpeed ZeRO stage 2/3 for parameter sharding, (3) Accelerate as the wrapper. Remote training (Colab T4/A100, Kaggle P100/T4x2): scripts/remote/colab_launcher.py builds notebook from a YAML config, uploads dataset reference, runs SFTTrainer, pushes checkpoint to HF Hub, retrieved locally and stamped into experiments/INDEX.md as if it were local. Key: keep the experiment manifest schema portable across compute targets.
