"""The scripts module must import and resolve paths inside the Docker image.

In the image the tree is /app/app/service/scripts.py: there is no repo root
above it. Indexing a fixed parent at import time used to raise IndexError and
crash the API on start.
"""

from pathlib import Path

from app.config import settings
from app.service import scripts

IMAGE_FILE = "/app/app/service/scripts.py"


def test_repo_root_does_not_raise_in_image_layout(monkeypatch):
    monkeypatch.setattr(scripts, "__file__", IMAGE_FILE)
    assert scripts._repo_root() == Path("/app")


def test_absolute_scripts_dir_is_used_as_is_in_image_layout(monkeypatch):
    monkeypatch.setattr(scripts, "__file__", IMAGE_FILE)
    monkeypatch.setattr(settings, "session_scripts_dir", "/srv/session-scripts")
    assert scripts.scripts_dir() == Path("/srv/session-scripts")


def test_relative_scripts_dir_resolves_from_repo_root_on_checkout():
    assert scripts.scripts_dir().name == "scripts"
    assert scripts.scripts_dir().is_dir()
