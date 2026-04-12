"""Static-asset path resolution + SPA-friendly cache headers.

Path helpers live here (not in main.py) so the CLI can import them without
triggering create_app() as a side effect.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import Scope


def _resolve_static_dir() -> Path:
    """Resolve static dir relative to the app package, cwd-independent."""
    return Path(__file__).resolve().parent.parent / "static"


def _assets_present() -> bool:
    return (_resolve_static_dir() / "index.html").is_file()


_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"


class CachingStaticFiles(StaticFiles):
    """Emit no-cache on index.html and long-lived immutable on assets/."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("assets/"):
                response.headers["cache-control"] = _IMMUTABLE
            else:
                response.headers["cache-control"] = _NO_CACHE
        return response
