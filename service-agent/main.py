#!/usr/bin/env python3
"""
Entrypoint for the Watch-my-pod AI Service Agent.
"""

import uvicorn
from app.server import app

if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
