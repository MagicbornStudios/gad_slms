import sys
from pathlib import Path

# Ensure src is in the path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from slm_from_scratch.models.dr_stein import DrSteinModel

# Load the model once globally so it doesn't reload the 124M weights for every single test case.
_model = None

def call_api(prompt, options, context):
    global _model
    if _model is None:
        _model = DrSteinModel()
        
    try:
        # Generate the response
        response = _model.generate(prompt, max_new_tokens=50, temperature=0.7)
        return {
            "output": response
        }
    except Exception as e:
        return {
            "error": str(e)
        }
