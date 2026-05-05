from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn
import torch.nn.functional as F

@dataclass
class LlamaConfig:
    vocab_size: int
    block_size: int = 2048
    n_layer: int = 30
    n_head: int = 9
    n_kv_head: int = 3
    n_embd: int = 576
    intermediate_size: int = 1536
    dropout: float = 0.0
    bias: bool = False
    rms_norm_eps: float = 1e-05
    rope_theta: float = 10000.0
    num_experts: int = 1
    num_experts_per_tok: int = 1
    gradient_checkpointing: bool = False

class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        var = x.pow(2).mean(-1, keepdim=True)
        return x * torch.rsqrt(var + self.eps) * self.weight

def precompute_freqs_cis(dim: int, end: int, theta: float = 10000.0):
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device, dtype=torch.float32)
    freqs = torch.outer(t, freqs)
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)
    return freqs_cis

def apply_rotary_emb(xq: torch.Tensor, xk: torch.Tensor, freqs_cis: torch.Tensor):
    xq_ = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_ = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))
    freqs_cis = freqs_cis.unsqueeze(0).unsqueeze(2) 
    xq_out = torch.view_as_real(xq_ * freqs_cis).flatten(3)
    xk_out = torch.view_as_real(xk_ * freqs_cis).flatten(3)
    return xq_out.type_as(xq), xk_out.type_as(xk)

class CausalSelfAttention(nn.Module):
    def __init__(self, config: LlamaConfig) -> None:
        super().__init__()
        if config.n_embd % config.n_head != 0:
            raise ValueError("n_embd must be divisible by n_head")
            
        self.n_head = config.n_head
        self.n_kv_head = config.n_kv_head
        self.n_rep = self.n_head // self.n_kv_head
        self.head_dim = config.n_embd // config.n_head
        self.dropout = config.dropout
        
        self.q_proj = nn.Linear(config.n_embd, config.n_head * self.head_dim, bias=config.bias)
        self.k_proj = nn.Linear(config.n_embd, config.n_kv_head * self.head_dim, bias=config.bias)
        self.v_proj = nn.Linear(config.n_embd, config.n_kv_head * self.head_dim, bias=config.bias)
        self.o_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        
        mask = torch.tril(torch.ones(config.block_size, config.block_size))
        self.register_buffer("bias", mask.view(1, 1, config.block_size, config.block_size))

    def forward(self, x: torch.Tensor, freqs_cis: torch.Tensor, past_key_value: tuple[torch.Tensor, torch.Tensor] | None = None) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        batch_size, seq_len, _ = x.size()
        
        q = self.q_proj(x).view(batch_size, seq_len, self.n_head, self.head_dim)
        k = self.k_proj(x).view(batch_size, seq_len, self.n_kv_head, self.head_dim)
        v = self.v_proj(x).view(batch_size, seq_len, self.n_kv_head, self.head_dim)
        
        q, k = apply_rotary_emb(q, k, freqs_cis)
        
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        if past_key_value is not None:
            past_k, past_v = past_key_value
            k = torch.cat((past_k, k), dim=-2)
            v = torch.cat((past_v, v), dim=-2)
            
        present_key_value = (k, v)
        
        if self.n_rep > 1:
            k = k[:, :, None, :, :].expand(batch_size, self.n_kv_head, self.n_rep, k.size(-2), self.head_dim).reshape(batch_size, self.n_head, k.size(-2), self.head_dim)
            v = v[:, :, None, :, :].expand(batch_size, self.n_kv_head, self.n_rep, v.size(-2), self.head_dim).reshape(batch_size, self.n_head, v.size(-2), self.head_dim)

        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))
        
        query_start = k.size(-2) - seq_len
        query_end = k.size(-2)
        key_len = k.size(-2)
        
        mask = self.bias[:, :, query_start:query_end, :key_len]
        att = att.masked_fill(mask == 0, float("-inf"))
        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)

        y = att @ v
        y = y.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)
        y = self.resid_dropout(self.o_proj(y))
        return y, present_key_value

class SwiGLUMLP(nn.Module):
    def __init__(self, config: LlamaConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.n_embd, config.intermediate_size, bias=config.bias)
        self.up_proj = nn.Linear(config.n_embd, config.intermediate_size, bias=config.bias)
        self.down_proj = nn.Linear(config.intermediate_size, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x)))

class MoEBlock(nn.Module):
    def __init__(self, config: LlamaConfig) -> None:
        super().__init__()
        self.num_experts = config.num_experts
        self.num_experts_per_tok = config.num_experts_per_tok
        self.gate = nn.Linear(config.n_embd, self.num_experts, bias=False)
        self.experts = nn.ModuleList([SwiGLUMLP(config) for _ in range(self.num_experts)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, hidden_dim = x.shape
        x_flat = x.view(-1, hidden_dim)
        
        router_logits = self.gate(x_flat)
        routing_weights = F.softmax(router_logits, dim=-1)
        routing_weights, selected_experts = torch.topk(routing_weights, self.num_experts_per_tok, dim=-1)
        routing_weights = routing_weights / routing_weights.sum(dim=-1, keepdim=True)
        
        final_hidden_states = torch.zeros_like(x_flat)
        
        for expert_idx in range(self.num_experts):
            expert_layer = self.experts[expert_idx]
            idx, top_x = torch.where(selected_experts == expert_idx)
            
            if idx.shape[0] == 0:
                continue
                
            current_state = x_flat[idx]
            current_hidden_states = expert_layer(current_state) * routing_weights[idx, top_x, None]
            final_hidden_states.index_add_(0, idx, current_hidden_states.to(current_state.dtype))
            
        return final_hidden_states.view(batch_size, seq_len, hidden_dim)

class LlamaBlock(nn.Module):
    def __init__(self, config: LlamaConfig) -> None:
        super().__init__()
        self.input_layernorm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)
        self.self_attn = CausalSelfAttention(config)
        self.post_attention_layernorm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)
        if config.num_experts > 1:
            self.mlp = MoEBlock(config)
        else:
            self.mlp = SwiGLUMLP(config)

    def forward(self, x: torch.Tensor, freqs_cis: torch.Tensor, past_key_value: tuple[torch.Tensor, torch.Tensor] | None = None) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        attn_out, present_key_value = self.self_attn(self.input_layernorm(x), freqs_cis, past_key_value=past_key_value)
        x = x + attn_out
        x = x + self.mlp(self.post_attention_layernorm(x))
        return x, present_key_value

class MiniLlama(nn.Module):
    def __init__(self, config: LlamaConfig) -> None:
        super().__init__()
        self.config = config
        self.embed_tokens = nn.Embedding(config.vocab_size, config.n_embd)
        self.dropout = nn.Dropout(config.dropout)
        self.layers = nn.ModuleList([LlamaBlock(config) for _ in range(config.n_layer)])
        self.norm = RMSNorm(config.n_embd, eps=config.rms_norm_eps)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        freqs_cis = precompute_freqs_cis(config.n_embd // config.n_head, config.block_size, config.rope_theta)
        self.register_buffer("freqs_cis", freqs_cis)

        self.gradient_checkpointing = config.gradient_checkpointing
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None, past_key_values: list[tuple[torch.Tensor, torch.Tensor]] | None = None) -> tuple[torch.Tensor, torch.Tensor | None, list[tuple[torch.Tensor, torch.Tensor]]]:
        batch_size, seq_len = idx.size()
        past_len = past_key_values[0][0].size(-2) if past_key_values is not None else 0
        total_len = past_len + seq_len

        if total_len > self.config.block_size:
            raise ValueError(f"Cannot forward sequence length {total_len}; block_size is {self.config.block_size}")

        x = self.embed_tokens(idx)
        x = self.dropout(x)
        
        freqs_cis = self.freqs_cis[past_len:total_len]
        
        present_key_values = []
        use_checkpoint = (
            self.gradient_checkpointing
            and self.training
            and past_key_values is None
        )
        for i, layer in enumerate(self.layers):
            past_kv = past_key_values[i] if past_key_values is not None else None
            if use_checkpoint:
                x = torch.utils.checkpoint.checkpoint(
                    lambda h, fc, blk=layer: blk(h, fc, past_key_value=None)[0],
                    x,
                    freqs_cis,
                    use_reentrant=False,
                )
                present_kv = None
            else:
                x, present_kv = layer(x, freqs_cis, past_key_value=past_kv)
            present_key_values.append(present_kv)
            
        x = self.norm(x)
        logits = self.lm_head(x)

        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss, present_key_values

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 0.8,
        top_k: int | None = 50,
    ) -> torch.Tensor:
        if temperature <= 0:
            raise ValueError("temperature must be greater than zero")
            
        past_key_values = None
        for _ in range(max_new_tokens):
            if past_key_values is not None:
                idx_cond = idx[:, -1:]
            else:
                idx_cond = idx
                if idx_cond.size(1) > self.config.block_size:
                    idx_cond = idx_cond[:, -self.config.block_size:]
                    
            logits, _, past_key_values = self(idx_cond, past_key_values=past_key_values)
            logits = logits[:, -1, :] / temperature
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, idx_next), dim=1)
            
            if past_key_values is not None and past_key_values[0][0].size(-2) >= self.config.block_size:
                past_key_values = None
                idx = idx[:, -self.config.block_size:]
                
        return idx

    @torch.no_grad()
    def generate_stream(
        self,
        idx: torch.Tensor,
        max_new_tokens: int,
        temperature: float = 0.8,
        top_k: int | None = 50,
    ):
        if temperature <= 0:
            raise ValueError("temperature must be greater than zero")
            
        past_key_values = None
        for _ in range(max_new_tokens):
            if past_key_values is not None:
                idx_cond = idx[:, -1:]
            else:
                idx_cond = idx
                if idx_cond.size(1) > self.config.block_size:
                    idx_cond = idx_cond[:, -self.config.block_size:]
                    
            logits, _, past_key_values = self(idx_cond, past_key_values=past_key_values)
            logits = logits[:, -1, :] / temperature
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")
            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, idx_next), dim=1)
            
            yield idx_next.item()
            
            if past_key_values is not None and past_key_values[0][0].size(-2) >= self.config.block_size:
                past_key_values = None
                idx = idx[:, -self.config.block_size:]

    def num_parameters(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())
