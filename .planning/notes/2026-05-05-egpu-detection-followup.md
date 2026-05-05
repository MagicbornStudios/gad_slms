# Razer Core eGPU not detected

User attached USB-C/Thunderbolt eGPU enclosure (Razer Core Chroma V2) with second GTX 1660 Ti on 2026-05-05. Both nvidia-smi and torch.cuda.device_count() report only 1 GPU. Likely causes: (1) Thunderbolt authorization not approved in Windows, (2) eGPU enclosure power cycle needed, (3) Razer Synapse driver missing, (4) cable not active TB3/TB4. Verify steps: check Device Manager for second 1660 Ti; if absent, follow Razer Core setup guide; reboot may be required. Until detected, all training assumptions stay single-GPU.
