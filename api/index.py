"""
Vercel Python Runtime entrypoint for the Flask backend.

This file exposes a WSGI `app` for Vercel by importing the Flask app
from the backend folder. It adjusts sys.path so that modules inside
`backend/` can be imported when executed from the `api/` directory.
It also rewrites PATH_INFO to include the "/api" prefix so that the
existing Flask routes like "/api/availability" continue to match when
served from Vercel's /api function mount point.
"""

import os
import sys
from typing import Callable


# Ensure the backend directory is on sys.path so we can import main.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
for p in (PROJECT_ROOT, BACKEND_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import the Flask app from backend/main.py
from backend.main import app as flask_app  # type: ignore  # noqa: E402


def _with_api_prefix(wsgi_app: Callable) -> Callable:
    """Wrap WSGI app so PATH_INFO is prefixed with '/api' if missing.

    On Vercel, requests to /api/foo invoke this function with PATH_INFO
    typically set to '/foo'. Our Flask routes are defined as '/api/...',
    so we add the '/api' prefix when absent.
    """

    def _app(environ, start_response):
        path = environ.get("PATH_INFO", "") or "/"
        if not path.startswith("/api/") and path != "/api":
            # Normalize duplicate slashes
            new_path = "/api" + (path if path.startswith("/") else f"/{path}")
            environ["PATH_INFO"] = new_path
        return wsgi_app(environ, start_response)

    return _app


# Expose `app` for Vercel (WSGI application)
app = _with_api_prefix(flask_app)
