import uvicorn
import os
import sys
from pathlib import Path

# Ensure root dir is on path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
import selectors

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from web.backend.app.config import API_HOST, API_PORT

def main():
    print(f"[Web API] Starting Ox-Loadout Server on http://{API_HOST}:{API_PORT}")
    print(f"[Web API] Swagger Documentation: http://{API_HOST}:{API_PORT}/docs")
    
    config = uvicorn.Config(
        "web.backend.app.main:app",
        host=API_HOST,
        port=API_PORT,
        loop="asyncio",
        reload=False,
    )
    server = uvicorn.Server(config)
    
    if sys.platform == "win32" and hasattr(selectors, "SelectSelector"):
        asyncio.run(server.serve(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(server.serve())

if __name__ == "__main__":
    main()
