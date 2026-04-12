import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[2] / "hatch_build.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("hatch_build", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_hook(root: Path, target_name: str):
    """Bypass BuildHookInterface.__init__ (signature varies across Hatchling versions)."""
    hook_mod = _load_hook()
    hook = hook_mod.FrontendBuildHook.__new__(hook_mod.FrontendBuildHook)
    # Name-mangled attrs backing the BuildHookInterface properties.
    hook._BuildHookInterface__root = str(root)
    hook._BuildHookInterface__target_name = target_name
    return hook


@pytest.fixture
def fake_repo(tmp_path):
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    backend.mkdir()
    (backend / "app").mkdir()
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name":"bc","scripts":{"build":"echo"}}')
    (frontend / "package-lock.json").write_text("{}")
    return tmp_path


def test_hook_no_op_for_unknown_target(fake_repo, monkeypatch):
    """Targets other than wheel/sdist (e.g., 'editable') must be a no-op."""
    hook = _make_hook(fake_repo / "backend", "editable")
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append((a, kw)))
    hook.initialize("standard", {})
    assert called == []
    assert not (fake_repo / "backend" / "app" / "static").exists()


def test_hook_builds_for_sdist(fake_repo, monkeypatch):
    """Sdist target triggers the frontend build so the sdist is self-contained."""
    frontend = fake_repo / "frontend"
    dist = frontend / "dist"

    def fake_run(argv, cwd=None, check=True, **kw):
        if argv[:2] == ["npm", "run"]:
            dist.mkdir(exist_ok=True)
            (dist / "index.html").write_text("<html>sdist-built</html>")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)

    hook = _make_hook(fake_repo / "backend", "sdist")
    hook.initialize("standard", {})

    static_dir = fake_repo / "backend" / "app" / "static"
    assert (static_dir / "index.html").read_text() == "<html>sdist-built</html>"


def test_hook_skips_when_prebuilt_and_no_frontend(tmp_path, monkeypatch):
    """Wheel-from-sdist: no ../frontend present, but app/static/index.html exists → skip."""
    backend = tmp_path / "backend"
    (backend / "app" / "static").mkdir(parents=True)
    (backend / "app" / "static" / "index.html").write_text("<html>prebuilt</html>")
    # Deliberately do NOT create tmp_path/frontend

    called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append(a))
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

    hook = _make_hook(backend, "wheel")
    hook.initialize("standard", {})

    assert called == []
    assert (backend / "app" / "static" / "index.html").read_text() == "<html>prebuilt</html>"


def test_hook_raises_when_no_frontend_and_no_prebuilt(tmp_path):
    """No ../frontend and no app/static → unbuildable, must raise."""
    backend = tmp_path / "backend"
    (backend / "app").mkdir(parents=True)
    hook = _make_hook(backend, "wheel")
    with pytest.raises(RuntimeError, match="cannot build frontend"):
        hook.initialize("standard", {})


def test_hook_raises_when_npm_missing(fake_repo, monkeypatch):
    hook = _make_hook(fake_repo / "backend", "wheel")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    with pytest.raises(RuntimeError, match="npm is required"):
        hook.initialize("standard", {})


def test_hook_copies_dist_on_success(fake_repo, monkeypatch):
    frontend = fake_repo / "frontend"
    dist = frontend / "dist"

    def fake_run(argv, cwd=None, check=True, **kw):
        if argv[:2] == ["npm", "run"]:
            dist.mkdir(exist_ok=True)
            (dist / "index.html").write_text("<html>built</html>")
            (dist / "assets").mkdir(exist_ok=True)
            (dist / "assets" / "app-x.js").write_text("x")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)

    hook = _make_hook(fake_repo / "backend", "wheel")
    hook.initialize("standard", {})

    static_dir = fake_repo / "backend" / "app" / "static"
    assert (static_dir / "index.html").read_text() == "<html>built</html>"
    assert (static_dir / "assets" / "app-x.js").read_text() == "x"


def test_hook_replaces_stale_static_dir(fake_repo, monkeypatch):
    frontend = fake_repo / "frontend"
    dist = frontend / "dist"
    static_dir = fake_repo / "backend" / "app" / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "stale.js").write_text("old")
    (static_dir / "index.html").write_text("<html>stale</html>")

    def fake_run(argv, cwd=None, check=True, **kw):
        if argv[:2] == ["npm", "run"]:
            dist.mkdir(exist_ok=True)
            (dist / "index.html").write_text("<html>fresh</html>")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)

    hook = _make_hook(fake_repo / "backend", "wheel")
    hook.initialize("standard", {})

    assert (static_dir / "index.html").read_text() == "<html>fresh</html>"
    assert not (static_dir / "stale.js").exists()


def test_hook_raises_when_build_emits_no_index(fake_repo, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

    def silent_run(argv, cwd=None, check=True, **kw):
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", silent_run)
    hook = _make_hook(fake_repo / "backend", "wheel")
    with pytest.raises(RuntimeError, match="index.html is missing"):
        hook.initialize("standard", {})


def test_hook_raises_when_npm_build_fails(fake_repo, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/" + cmd)

    def failing_run(argv, cwd=None, check=True, **kw):
        raise subprocess.CalledProcessError(1, argv, stderr=b"build failed")

    monkeypatch.setattr(subprocess, "run", failing_run)
    hook = _make_hook(fake_repo / "backend", "wheel")
    with pytest.raises(subprocess.CalledProcessError):
        hook.initialize("standard", {})
