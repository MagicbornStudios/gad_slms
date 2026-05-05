# Phase 02: Architecture Refactor & Observability

This document establishes the binding implementation decisions for Phase 02, derived from the `gad-discuss-phase` workflow. Downstream planners and builders must adhere to these constraints.

## 1. One Component, One File = One Concern
`scripts/learning_tui/chat_screen.py` will be dismantled. It currently handles UI, model routing, slash commands, and speech capture.
- **Decision:** Split into:
  - `chat_screen.py` (Shell/Orchestrator)
  - `components/chat_composer.py` (Input & Speech)
  - `components/chat_log.py` (Message rendering)
  - `logic/slash_commands.py` (Levenshtein routing)
  - `logic/model_runner.py` (Async generation & Caching)

## 2. Textual TUI Formatting Constraints
- **Decision:** Remove all hardcoded `height: <int>` attributes from flexible containers (like `#chat-suggestions`, `#menu-details`) in `06_learning_tui.css`. Use `1fr` and `auto` sizing to ensure the UI scales gracefully when the terminal window is collapsed or resized.

## 3. Observability & Telemetry (The "Gilgamesh" Standard)
Dr. Stein and Kael must operate within the `gad` tracking ecosystem.
- **Decision:** Introduce `scripts/learning_tui/telemetry.py`. All agent tool calls and generation metrics (time to first token, generation speed) will be written to a `.gad-log` JSONL file. 

## 4. Performance Optimization (Kael's Latency)
- **Decision:** The current `chat_screen.py` waits for the *entire* model generation to finish before artificially streaming characters. We will update the `KaelModel` and `model_runner.py` to yield tokens lazily via a Python Generator, passing them back to the TUI instantly to eliminate the perceived lag.

## 5. Autonomous MoE Handoffs
- **Decision:** Implement a basic system tool interceptor. If Kael outputs a specific trigger (e.g., `<|tool_call|>switch_dr_stein`), the TUI will autonomously execute the hot-swap instead of requiring the user to type `/model dr_stein`.
