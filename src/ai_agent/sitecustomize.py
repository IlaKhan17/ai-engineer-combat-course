from __future__ import annotations

# This file is auto-imported by Python at startup (if it exists on sys.path).
# When you run `uvicorn src.ai_agent.main:app` from inside `src/ai_agent/`,
# the repo root might not be on sys.path, which breaks `import src...`.
#
# Fix: ensure the repo root is on sys.path so `src` is importable.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

