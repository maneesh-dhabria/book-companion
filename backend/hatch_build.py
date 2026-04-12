"""Custom Hatchling build hook: build the Vue SPA and bundle it into the wheel."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-build"

    def initialize(self, version: str, build_data: dict) -> None:
        # Only run for wheel target. Sdist ships source; consumers build themselves.
        if self.target_name != "wheel":
            return

        backend_root = Path(self.root)  # backend/
        frontend_dir = backend_root.parent / "frontend"
        dist_dir = frontend_dir / "dist"
        static_dir = backend_root / "app" / "static"
        lockfile = frontend_dir / "package-lock.json"

        if shutil.which("npm") is None:
            raise RuntimeError(
                "npm is required to build the frontend for the wheel. "
                "Install Node.js >=18 or build without the wheel target."
            )

        install_cmd = ["npm", "ci"] if lockfile.exists() else ["npm", "install"]
        subprocess.run(install_cmd, cwd=str(frontend_dir), check=True)

        # Clear dist/ before build so a mid-build failure can't leave stale
        # files that silently get copied into the wheel on retry.
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)

        if not (dist_dir / "index.html").is_file():
            raise RuntimeError(
                f"npm run build completed but {dist_dir / 'index.html'} is missing. "
                "Check frontend/vite.config.* for a non-default outDir."
            )

        if static_dir.exists():
            shutil.rmtree(static_dir)
        shutil.copytree(dist_dir, static_dir)
