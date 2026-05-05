import json
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / ".gad" / "logs"
LOG_FILE = LOG_DIR / "agent-telemetry.jsonl"
HANDOFFS_DIR = ROOT / ".planning" / "handoffs"

def init_telemetry():
    """Ensure the logging and handoff directories exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ["open", "claimed", "closed"]:
        (HANDOFFS_DIR / sub).mkdir(parents=True, exist_ok=True)

def log_event(event_type: str, agent_name: str, payload: Dict[str, Any]):
    """Log an agent event to the global GAD telemetry file."""
    init_telemetry()
    
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event_type": event_type,
        "agent": agent_name,
        "payload": payload
    }
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

def check_handoffs(agent_name: str) -> list[str]:
    """Basic check for open handoffs."""
    init_telemetry()
    open_dir = HANDOFFS_DIR / "open"
    return [f.name for f in open_dir.glob("*.md")]

# Initialize on import
init_telemetry()
