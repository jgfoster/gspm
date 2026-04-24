"""Git subprocess wrapper for Geode."""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from geode.errors import GitError


def clone_bare(url: str, dest: Path) -> None:
    """Clone a bare repository to dest."""
    if dest.exists():
        # Already cloned, fetch updates instead
        _run_git("fetch", "--all", "--tags", cwd=dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run_git("clone", "--bare", url, str(dest))


def fetch_tags(repo_path: Path) -> None:
    """Fetch all tags from remote."""
    _run_git("fetch", "--tags", cwd=repo_path)


def list_tags(repo_path: Path) -> List[str]:
    """Return all tag names."""
    result = _run_git("tag", "--list", cwd=repo_path)
    return [t.strip() for t in result.stdout.splitlines() if t.strip()]


def ls_remote_tags(url: str) -> Dict[str, str]:
    """List remote tags without cloning. Returns {tag_name: sha}."""
    result = _run_git("ls-remote", "--tags", url)
    tags: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        sha, ref = line.split(None, 1)
        # Skip ^{} dereferenced tag entries
        if ref.endswith("^{}"):
            # Use the dereferenced SHA (points to the commit)
            tag_name = ref.replace("refs/tags/", "").replace("^{}", "")
            tags[tag_name] = sha
        elif ref.replace("refs/tags/", "") not in tags:
            tag_name = ref.replace("refs/tags/", "")
            tags[tag_name] = sha
    return tags


def checkout_tree(repo_path: Path, sha: str, dest: Path) -> None:
    """Extract a specific SHA's tree into dest directory.

    Uses git archive to extract without a full checkout.
    """
    dest.mkdir(parents=True, exist_ok=True)
    archive = _run_git("archive", sha, cwd=repo_path)
    subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        input=archive.stdout,
        check=True,
        capture_output=True,
    )


def resolve_ref(repo_path: Path, ref: str) -> str:
    """Resolve a ref (tag, branch, HEAD) to a full SHA."""
    result = _run_git("rev-parse", ref, cwd=repo_path)
    return result.stdout.strip()


def read_file_at_ref(repo_path: Path, ref: str, file_path: str) -> str:
    """Read a file from a specific ref without checkout.

    Uses `git show <ref>:<file_path>`.
    """
    result = _run_git("show", f"{ref}:{file_path}", cwd=repo_path)
    return result.stdout


def _run_git(
    *args: str, cwd: Optional[Path] = None
) -> subprocess.CompletedProcess:
    """Run a git command, raising GitError on failure."""
    cmd = ["git"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not in PATH")

    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")

    return result
