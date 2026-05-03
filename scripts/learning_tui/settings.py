from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
VCS_ENABLED = os.getenv("SLM_TUI_VCS", "1").lower() not in {"0", "false", "no", "off"}
