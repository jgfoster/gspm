"""Lightweight GitHub-based package registry for Geode.

The registry is a git repository containing an index.json file that maps
package names to their git URLs and published versions.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Optional

from geode.config import DEFAULT_REGISTRY, GLOBAL_CONFIG_DIR
from geode.errors import RegistryError
from geode.models import Dependency, Manifest, RegistryEntry
from geode import git as git_ops

REGISTRY_CACHE_DIR = GLOBAL_CONFIG_DIR / "registry"
INDEX_FILE = "index.json"


def fetch_index(registry_url: str = DEFAULT_REGISTRY) -> Dict[str, RegistryEntry]:
    """Fetch and parse the registry index.

    Clones or updates the registry repo in ~/.geode/registry/ and
    reads index.json. Returns a dict of package_name -> RegistryEntry.
    """
    _ensure_registry_clone(registry_url)
    index_path = REGISTRY_CACHE_DIR / INDEX_FILE

    if not index_path.exists():
        raise RegistryError(
            f"Registry index not found at {index_path}. "
            f"The registry at {registry_url} may be empty or misconfigured."
        )

    try:
        data = json.loads(index_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise RegistryError(f"Failed to parse registry index: {e}") from e

    entries: Dict[str, RegistryEntry] = {}
    for name, info in data.items():
        entries[name] = RegistryEntry(
            name=name,
            git=info.get("git", ""),
            versions=info.get("versions", []),
            description=info.get("description", ""),
        )

    return entries


def lookup_package(
    name: str, registry_url: str = DEFAULT_REGISTRY
) -> Optional[RegistryEntry]:
    """Look up a single package in the registry."""
    index = fetch_index(registry_url)
    return index.get(name)


def resolve_git_url(
    name: str, dep: Dependency, registry_url: str = DEFAULT_REGISTRY
) -> str:
    """Resolve a package name to a git URL.

    If dep.git is set, use it directly.
    Otherwise, look up in the registry.
    """
    if dep.git:
        return dep.git

    entry = lookup_package(name, registry_url)
    if entry is None:
        raise RegistryError(
            f"Package '{name}' not found in registry. "
            f"Specify a git URL with --git or publish the package first."
        )
    return entry.git


def publish_package(
    manifest: Manifest,
    project_root: Path,
    registry_url: str = DEFAULT_REGISTRY,
) -> str:
    """Publish the current package to the registry.

    1. Validates the manifest.
    2. Ensures the version tag exists in git.
    3. Updates the local registry index.
    4. Opens a PR to the registry repo using `gh` CLI.

    Returns the PR URL.
    """
    name = manifest.package.name
    version = manifest.package.version
    repo_url = manifest.package.repository

    if not repo_url:
        raise RegistryError(
            "Cannot publish: 'repository' field is missing from [package] "
            "in gemstone.toml."
        )

    # Verify version tag exists
    tag = f"v{version}"
    try:
        git_ops.resolve_ref(project_root, tag)
    except Exception:
        raise RegistryError(
            f"Version tag '{tag}' not found. "
            f"Create a git tag before publishing: git tag {tag}"
        )

    # Update registry index
    _ensure_registry_clone(registry_url)
    index_path = REGISTRY_CACHE_DIR / INDEX_FILE

    if index_path.exists():
        data = json.loads(index_path.read_text())
    else:
        data = {}

    if name in data:
        entry = data[name]
        if version in entry.get("versions", []):
            raise RegistryError(
                f"Version {version} of '{name}' is already published."
            )
        entry["versions"].insert(0, version)
        entry["git"] = repo_url
        if manifest.package.description:
            entry["description"] = manifest.package.description
    else:
        data[name] = {
            "git": repo_url,
            "versions": [version],
            "description": manifest.package.description,
        }

    index_path.write_text(json.dumps(data, indent=2) + "\n")

    # Create branch, commit, and open PR via gh CLI
    branch = f"publish/{name}/{version}"
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=REGISTRY_CACHE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", INDEX_FILE],
            cwd=REGISTRY_CACHE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Publish {name} {version}"],
            cwd=REGISTRY_CACHE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=REGISTRY_CACHE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )

        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--title", f"Publish {name} {version}",
                "--body", f"Add {name} {version} to the Geode registry.\n\n"
                          f"Repository: {repo_url}\n"
                          f"Description: {manifest.package.description}",
            ],
            cwd=REGISTRY_CACHE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    except FileNotFoundError:
        raise RegistryError(
            "The `gh` CLI is required for publishing. "
            "Install it from https://cli.github.com/"
        )
    except subprocess.CalledProcessError as e:
        raise RegistryError(
            f"Failed to create PR: {e.stderr.strip()}"
        ) from e


def _ensure_registry_clone(registry_url: str) -> None:
    """Clone or update the registry repository."""
    REGISTRY_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    git_dir = REGISTRY_CACHE_DIR / ".git"
    if git_dir.exists():
        # Already cloned — pull updates
        try:
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=REGISTRY_CACHE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=REGISTRY_CACHE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            pass  # Best-effort update
    else:
        # Fresh clone
        try:
            subprocess.run(
                ["git", "clone", registry_url, str(REGISTRY_CACHE_DIR)],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RegistryError(
                f"Failed to clone registry from {registry_url}: {e.stderr.strip()}"
            ) from e
