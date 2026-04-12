
import pytest

from app.api import static_files


@pytest.fixture(autouse=True)
def _clear_api_only(monkeypatch):
    monkeypatch.delenv("BOOKCOMPANION_API_ONLY", raising=False)


def test_static_dir_resolves_to_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = static_files._resolve_static_dir()
    assert resolved.is_absolute()
    assert resolved.parts[-2:] == ("app", "static")
    assert not str(resolved).startswith(str(tmp_path))


def test_assets_present_false_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
    assert static_files._assets_present() is False


def test_assets_present_true_when_index_exists(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setattr(static_files, "_resolve_static_dir", lambda: tmp_path)
    assert static_files._assets_present() is True


def test_create_app_mounts_static_when_present(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html></html>")
    import app.api.main as api_main

    monkeypatch.setattr(api_main, "_assets_present", lambda: True)
    monkeypatch.setattr(api_main, "_resolve_static_dir", lambda: tmp_path)
    app = api_main.create_app()
    static_mounts = [r for r in app.routes if getattr(r, "name", "") == "static"]
    assert len(static_mounts) == 1


def test_create_app_skips_mount_when_missing(tmp_path, monkeypatch):
    import app.api.main as api_main

    monkeypatch.setattr(api_main, "_assets_present", lambda: False)
    monkeypatch.setattr(api_main, "_resolve_static_dir", lambda: tmp_path)
    app = api_main.create_app()
    static_mounts = [r for r in app.routes if getattr(r, "name", "") == "static"]
    assert len(static_mounts) == 0
