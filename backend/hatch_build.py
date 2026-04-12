"""Custom Hatchling build hook: build the Vue SPA and bundle it into the wheel/sdist."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-build"

    def initialize(self, version: str, build_data: dict) -> None:
        # Run for both wheel and sdist so sdists are self-contained (carry prebuilt
        # assets) and wheels built from extracted sdists find them already in-tree.
        if self.target_name not in ("wheel", "sdist"):
            return

        backend_root = Path(self.root)  # backend/
        frontend_dir = backend_root.parent / "frontend"
        dist_dir = frontend_dir / "dist"
        static_dir = backend_root / "app" / "static"
        lockfile = frontend_dir / "package-lock.json"
        frontend_available = (frontend_dir / "package.json").is_file()
        prebuilt = (static_dir / "index.html").is_file()

        # Wheel-from-sdist path: no source tree, but prebuilt assets already in-tree.
        if not frontend_available:
            if prebuilt:
                return
            raise RuntimeError(
                f"cannot build frontend: {frontend_dir} is missing and no prebuilt "
                f"assets at {static_dir}. If building from sdist, the sdist is malformed."
            )

        # Fresh source path: build.
        if shutil.which("npm") is None:
            raise RuntimeError(
                "npm is required to build the frontend for the wheel/sdist. "
                "Install Node.js >=18 or build without needing npm."
            )

        install_cmd = ["npm", "ci"] if lockfile.exists() else ["npm", "install"]
        subprocess.run(install_cmd, cwd=str(frontend_dir), check=True)

        # Clear dist/ before build so a mid-build failure can't leave stale files.
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
