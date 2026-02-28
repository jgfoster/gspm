"""Manage .gspm/cache and .gspm/deps directories."""

import shutil
from pathlib import Path

from gspm.errors import CacheError
from gspm.models import Lockfile

GSPM_DIR = ".gspm"
CACHE_DIR = ".gspm/cache"
DEPS_DIR = ".gspm/deps"
BARE_DIR = ".gspm/bare"
TONEL_DIR = ".gspm/tonel"


def ensure_dirs(project_root: Path) -> None:
    """Create .gspm directories if they don't exist."""
    for subdir in (CACHE_DIR, DEPS_DIR, BARE_DIR, TONEL_DIR):
        (project_root / subdir).mkdir(parents=True, exist_ok=True)


def tonel_output_path(project_root: Path, package_name: str) -> Path:
    """Return the output directory for transpiled Tonel .tpz files."""
    return project_root / TONEL_DIR / package_name


def bare_repo_path(project_root: Path, name: str) -> Path:
    """Return the path to a bare repo clone for a dependency."""
    return project_root / BARE_DIR / f"{name}.git"


def is_cached(project_root: Path, sha: str) -> bool:
    """Check if a SHA's tree is already in the cache."""
    return (project_root / CACHE_DIR / sha).is_dir()


def cache_path(project_root: Path, sha: str) -> Path:
    """Return the cache path for a SHA."""
    return project_root / CACHE_DIR / sha


def populate_deps(project_root: Path, lockfile: Lockfile) -> None:
    """Populate .gspm/deps/ from cache based on lockfile."""
    deps_dir = project_root / DEPS_DIR

    # Clean existing deps
    if deps_dir.exists():
        shutil.rmtree(deps_dir)
    deps_dir.mkdir(parents=True)

    for pkg in lockfile.packages:
        src = project_root / CACHE_DIR / pkg.sha
        if not src.is_dir():
            raise CacheError(
                f"Cache missing for {pkg.name} ({pkg.sha}). Run 'gspm fetch' first."
            )
        dest = deps_dir / pkg.name
        # Copy from cache to deps
        shutil.copytree(src, dest)


def get_dep_path(project_root: Path, name: str) -> Path:
    """Return the path to a dependency's working copy."""
    return project_root / DEPS_DIR / name


def clean_deps(project_root: Path) -> None:
    """Remove .gspm/deps/."""
    deps_dir = project_root / DEPS_DIR
    if deps_dir.exists():
        shutil.rmtree(deps_dir)


def clean_all(project_root: Path) -> None:
    """Remove entire .gspm/ directory."""
    gspm_dir = project_root / GSPM_DIR
    if gspm_dir.exists():
        shutil.rmtree(gspm_dir)
