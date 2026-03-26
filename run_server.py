from __future__ import annotations

# Start the FastAPI server in a way that always works regardless of your
# current working directory.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "src.ai_agent.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

