# Architecture exploration after Stage 2.5

Try increasing n_head (9 -> 12 or 16) and n_embd (576 -> 640 or 768) within the 6GB VRAM ceiling. Goal: more reasoning capacity per token. Constraint: full pipeline (load + train batch + activations + grads) must still fit on baseline GPU. Measure reasoning eval lift per added param.
