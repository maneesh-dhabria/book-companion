"""Static-asset path resolution + SPA-friendly cache headers.

Path helpers live here (not in main.py) so the CLI can import them without
triggering create_app() as a side effect.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

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

# Missing asset-extension paths should 404 instead of falling back to index.html.
_ASSET_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".mp4",
    ".webm",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".map",
)


class CachingStaticFiles(StaticFiles):
    """Emit no-cache on index.html and long-lived immutable on assets/."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
            status = response.status_code
        except (HTTPException, StarletteHTTPException) as exc:
            if (
                exc.status_code != 404
                or path.startswith("assets/")
                or path.lower().endswith(_ASSET_EXTENSIONS)
            ):
                raise
            response = await super().get_response("index.html", scope)
            status = response.status_code

        # SPA fallback on 404 returned as a response (rare path).
        if (
            status == 404
            and not path.startswith("assets/")
            and not path.lower().endswith(_ASSET_EXTENSIONS)
        ):
            response = await super().get_response("index.html", scope)
            status = response.status_code

        if status == 200:
            if path.startswith("assets/"):
                response.headers["cache-control"] = _IMMUTABLE
            else:
                response.headers["cache-control"] = _NO_CACHE
        return response
