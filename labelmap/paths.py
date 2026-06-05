"""Filesystem paths for bundled assets and runtime directories."""

import os
import sys
from pathlib import Path


def app_dir():
    """App root: PyInstaller bundle dir, env override, or script directory."""
    env_dir = os.environ.get("LABELMAP_APP_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def repo_root():
    """Repository root (parent of the labelmap package)."""
    return Path(__file__).resolve().parent.parent


def template_file_path():
    """Locate bundled map.xlsx for sample data and template download."""
    name = "map.xlsx"
    search_dirs = []
    env_dir = os.environ.get("LABELMAP_APP_DIR")
    if env_dir:
        search_dirs.append(Path(env_dir))
    root = repo_root()
    search_dirs.extend(
        [
            root,
            root / "data",
            Path(app_dir()).resolve().parent,
            Path(__file__).resolve().parent.parent,
            Path.cwd(),
        ]
    )
    seen = set()
    for base in search_dirs:
        base = base.resolve()
        if base in seen:
            continue
        seen.add(base)
        path = base / name
        if path.is_file():
            return str(path)
    return None


def playwright_browsers_path():
    return os.path.join(repo_root(), ".playwright-browsers")
