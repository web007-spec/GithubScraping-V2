#!/usr/bin/env python3
"""
Start the API bound to all interfaces (0.0.0.0) for LAN access.

On Windows, auto-reload is OFF by default (avoids multiprocessing spawn errors).
To enable reload: set API_RELOAD=true before running.
"""

from __future__ import annotations

import os
import platform
import socket
import sys


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _use_reload() -> bool:
    flag = os.getenv("API_RELOAD", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    # Default: no reload on Windows (multiprocessing spawn + pydantic issues)
    return platform.system() != "Windows"


def main() -> None:
    import uvicorn

    from app.config import get_settings

    settings = get_settings()
    reload = _use_reload()
    ip = lan_ip()

    print(f"API listening on all interfaces: http://{ip}:{settings.api_port}")
    print(f"  Local:  http://127.0.0.1:{settings.api_port}")
    print(f"  Health: http://{ip}:{settings.api_port}/health")
    if platform.system() == "Windows" and not reload:
        print("  (Windows: reload disabled. Set API_RELOAD=true to enable.)")

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
        log_level="info",
    )


if __name__ == "__main__":
    if platform.system() == "Windows":
        import multiprocessing

        multiprocessing.freeze_support()
    main()
