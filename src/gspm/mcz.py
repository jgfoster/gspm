"""Migration shim for Monticello (.mcz) packages.

Extracts a .mcz archive, locates ``snapshot/source.st`` (Smalltalk chunk
format), and produces a gspm package directory with a ``gemstone.toml``
and the source as a ``.gs`` file. Topaz can ``input`` chunk-format files
directly, so chunk-level parsing is not required for the round-trip;
this module performs only minimal cleanup of Monticello-specific
metadata that Topaz does not understand.

This is a best-effort onboarding aid. Complex Monticello packages
(traits, unusual extensions, non-standard metadata) may still need
manual review of the output.
"""

import re
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from gspm.errors import MczError


# Strip Monticello stamp metadata that Topaz `input` does not recognize:
#   methodsFor: 'foo' stamp: 'author 1/2/3'
#   commentStamp: '...' prior: ...
_STAMP_RE = re.compile(r"\s+(?:stamp|commentStamp):\s*'[^']*'")
_PRIOR_RE = re.compile(r"\s+prior:\s+\d+")
_PACKAGE_NAME_RE = re.compile(r"name\s+'([^']+)'")


def migrate_mcz(mcz_path: Path, out_dir: Path) -> Path:
    """Convert a .mcz archive into a gspm package at ``out_dir``.

    Returns the path to the generated ``gemstone.toml``.
    """
    if not mcz_path.exists():
        raise MczError(f"File not found: {mcz_path}")
    if not zipfile.is_zipfile(mcz_path):
        raise MczError(f"Not a valid .mcz archive: {mcz_path}")

    package_name, source_text = _extract_mcz(mcz_path)
    cleaned = _clean_chunk_source(source_text)

    out_dir.mkdir(parents=True, exist_ok=True)
    src_dir = out_dir / "src"
    src_dir.mkdir(exist_ok=True)

    gs_file = src_dir / f"{package_name}.gs"
    gs_file.write_text(cleaned)

    manifest_path = out_dir / "gemstone.toml"
    manifest_path.write_text(
        _generate_manifest(package_name, gs_file.relative_to(out_dir))
    )

    return manifest_path


def _extract_mcz(mcz_path: Path) -> Tuple[str, str]:
    """Pull the package name and source.st text out of an .mcz archive."""
    with zipfile.ZipFile(mcz_path) as zf:
        names = zf.namelist()

        source_name = None
        for candidate in ("snapshot/source.st", "source.st"):
            if candidate in names:
                source_name = candidate
                break
        if source_name is None:
            for n in names:
                if n.endswith("source.st"):
                    source_name = n
                    break
        if source_name is None:
            raise MczError(
                f"No source.st found in {mcz_path.name}; "
                "is this a valid Monticello package?"
            )

        source_bytes = zf.read(source_name)
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError:
            source_text = source_bytes.decode("latin-1")

        package_name: Optional[str] = None
        for candidate in ("package", "snapshot/package"):
            if candidate in names:
                pkg_text = zf.read(candidate).decode("utf-8", errors="replace")
                package_name = _parse_package_name(pkg_text)
                if package_name:
                    break
        if not package_name:
            package_name = _name_from_filename(mcz_path.stem)

    return package_name, source_text


def _parse_package_name(pkg_text: str) -> Optional[str]:
    """Extract the package name from a Monticello ``package`` file.

    The file contains a STON-like literal of the form ``(name 'MyPkg')``.
    """
    m = _PACKAGE_NAME_RE.search(pkg_text)
    return m.group(1) if m else None


def _name_from_filename(stem: str) -> str:
    """Strip a ``-author.version`` suffix from an .mcz filename stem."""
    # Common Monticello pattern: PackageName-author.42
    if "-" in stem:
        head, _, tail = stem.rpartition("-")
        if "." in tail and head:
            return head
    return stem


def _clean_chunk_source(text: str) -> str:
    """Strip Monticello metadata Topaz doesn't understand."""
    text = _STAMP_RE.sub("", text)
    text = _PRIOR_RE.sub("", text)
    return text


def _generate_manifest(package_name: str, gs_relpath: Path) -> str:
    return f'''[package]
name = "{_normalize_name(package_name)}"
version = "0.1.0"
description = "Migrated from Monticello package {package_name}"
gemstone = ">=3.5"

[load]
files = ["{gs_relpath.as_posix()}"]

[dependencies]

[dev-dependencies]

[test]
files = []
'''


def _normalize_name(name: str) -> str:
    """Convert a Monticello CamelCase package name to lowercase-with-hyphens."""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("-")
        out.append(ch.lower())
    return "".join(out).strip("-")
