"""Parse and write gemstone.toml manifest files."""

from pathlib import Path
from typing import Dict, List, Optional

import tomlkit
from packaging.specifiers import SpecifierSet

from gspm.errors import ManifestError
from gspm.models import (
    Dependency,
    LoadSpec,
    Manifest,
    PackageMetadata,
    SuiteSpec,
)


def load_manifest(path: Path) -> Manifest:
    """Parse gemstone.toml into a Manifest."""
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        doc = tomlkit.loads(path.read_text())
    except Exception as e:
        raise ManifestError(f"Invalid TOML in {path}: {e}") from e

    # [package] — required
    pkg_table = doc.get("package")
    if not pkg_table:
        raise ManifestError("Missing [package] section in gemstone.toml")

    for field in ("name", "version"):
        if field not in pkg_table:
            raise ManifestError(f"Missing required field: package.{field}")

    package = PackageMetadata(
        name=pkg_table["name"],
        version=pkg_table["version"],
        description=pkg_table.get("description", ""),
        gemstone=pkg_table.get("gemstone", ""),
        authors=list(pkg_table.get("authors", [])),
        license=pkg_table.get("license", ""),
        repository=pkg_table.get("repository", ""),
    )

    # [load]
    load_table = doc.get("load", {})
    load_conditions = {}
    if "conditions" in load_table:
        for key, files in load_table["conditions"].items():
            load_conditions[key] = list(files)

    load = LoadSpec(
        files=list(load_table.get("files", [])),
        tonel=list(load_table.get("tonel", [])),
        filetree=list(load_table.get("filetree", [])),
        conditions=load_conditions,
    )

    # [dependencies]
    dependencies = _parse_dependencies(doc.get("dependencies", {}))

    # [dev-dependencies]
    dev_dependencies = _parse_dependencies(doc.get("dev-dependencies", {}))

    # [test]
    test_table = doc.get("test", {})
    test = SuiteSpec(files=list(test_table.get("files", [])))

    return Manifest(
        package=package,
        load=load,
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
        test=test,
    )


def save_manifest(manifest: Manifest, path: Path) -> None:
    """Write a Manifest to gemstone.toml."""
    doc = tomlkit.document()

    # [package]
    pkg = tomlkit.table()
    pkg.add("name", manifest.package.name)
    pkg.add("version", manifest.package.version)
    if manifest.package.description:
        pkg.add("description", manifest.package.description)
    if manifest.package.gemstone:
        pkg.add("gemstone", manifest.package.gemstone)
    if manifest.package.authors:
        pkg.add("authors", manifest.package.authors)
    if manifest.package.license:
        pkg.add("license", manifest.package.license)
    if manifest.package.repository:
        pkg.add("repository", manifest.package.repository)
    doc.add("package", pkg)

    # [load]
    if manifest.load.files or manifest.load.tonel or manifest.load.filetree or manifest.load.conditions:
        load = tomlkit.table()
        if manifest.load.files:
            load.add("files", manifest.load.files)
        if manifest.load.tonel:
            load.add("tonel", manifest.load.tonel)
        if manifest.load.filetree:
            load.add("filetree", manifest.load.filetree)
        if manifest.load.conditions:
            conditions = tomlkit.table()
            for key, files in manifest.load.conditions.items():
                conditions.add(key, files)
            load.add("conditions", conditions)
        doc.add("load", load)

    # [dependencies]
    if manifest.dependencies:
        deps = tomlkit.table()
        for name, dep in manifest.dependencies.items():
            deps.add(name, _dep_to_inline_table(dep))
        doc.add("dependencies", deps)

    # [dev-dependencies]
    if manifest.dev_dependencies:
        dev_deps = tomlkit.table()
        for name, dep in manifest.dev_dependencies.items():
            dev_deps.add(name, _dep_to_inline_table(dep))
        doc.add("dev-dependencies", dev_deps)

    # [test]
    if manifest.test.files:
        test = tomlkit.table()
        test.add("files", manifest.test.files)
        doc.add("test", test)

    path.write_text(tomlkit.dumps(doc))


def add_dependency(
    path: Path,
    name: str,
    version: str,
    git: str = "",
    dev: bool = False,
    files: Optional[List[str]] = None,
    tonel: Optional[List[str]] = None,
    filetree: Optional[List[str]] = None,
) -> None:
    """Add a dependency to gemstone.toml in-place (round-trip edit)."""
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    doc = tomlkit.loads(path.read_text())
    section = "dev-dependencies" if dev else "dependencies"

    if section not in doc:
        doc.add(section, tomlkit.table())

    inline = tomlkit.inline_table()
    inline.append("version", version)
    if git:
        inline.append("git", git)
    if files:
        inline.append("files", files)
    if tonel:
        inline.append("tonel", tonel)
    if filetree:
        inline.append("filetree", filetree)
    doc[section][name] = inline

    path.write_text(tomlkit.dumps(doc))


def scaffold_manifest(name: str) -> str:
    """Return the content of a skeleton gemstone.toml for `gspm init`."""
    return f'''[package]
name = "{name}"
version = "0.1.0"
description = ""
gemstone = ">=3.5"
authors = []
license = "MIT"

[load]
files = [
    "src/{name}.gs",
]

[dependencies]

[dev-dependencies]

[test]
files = []
'''


def expand_constraint(version_str: str) -> str:
    """Convert Cargo-style version constraints to PEP 440 specifiers.

    ^1.2.3  -> >=1.2.3,<2.0.0
    ^0.2.3  -> >=0.2.3,<0.3.0
    ^0.0.3  -> >=0.0.3,<0.0.4
    ~1.2.3  -> >=1.2.3,<1.3.0
    *       -> >=0
    >=3.5   -> >=3.5    (passthrough)
    """
    s = version_str.strip()

    if s == "*":
        return ">=0"

    if s.startswith("^"):
        return _expand_caret(s[1:])

    if s.startswith("~"):
        return _expand_tilde(s[1:])

    # Already PEP 440 compatible — validate and return
    try:
        SpecifierSet(s)
    except Exception:
        raise ManifestError(f"Invalid version constraint: {version_str}")
    return s


def _expand_caret(version: str) -> str:
    """Expand ^X.Y.Z to >=X.Y.Z,<upper."""
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 3:
        parts.append(0)

    major, minor, patch = parts[0], parts[1], parts[2]

    if major != 0:
        upper = f"{major + 1}.0.0"
    elif minor != 0:
        upper = f"0.{minor + 1}.0"
    else:
        upper = f"0.0.{patch + 1}"

    return f">={version},<{upper}"


def _expand_tilde(version: str) -> str:
    """Expand ~X.Y.Z to >=X.Y.Z,<X.(Y+1).0."""
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 3:
        parts.append(0)

    major, minor = parts[0], parts[1]
    return f">={version},<{major}.{minor + 1}.0"


def _parse_dependencies(table: dict) -> Dict[str, Dependency]:
    """Parse a [dependencies] or [dev-dependencies] table."""
    deps: Dict[str, Dependency] = {}
    for name, spec in table.items():
        if isinstance(spec, str):
            deps[name] = Dependency(name=name, version=spec)
        elif isinstance(spec, dict):
            deps[name] = Dependency(
                name=name,
                version=spec.get("version", "*"),
                git=spec.get("git", ""),
                files=list(spec.get("files", [])),
                tonel=list(spec.get("tonel", [])),
                filetree=list(spec.get("filetree", [])),
            )
        else:
            raise ManifestError(
                f"Invalid dependency spec for '{name}': expected string or table"
            )
    return deps


def _dep_to_inline_table(dep: Dependency) -> tomlkit.items.InlineTable:
    """Convert a Dependency to a TOML inline table."""
    inline = tomlkit.inline_table()
    inline.append("version", dep.version)
    if dep.git:
        inline.append("git", dep.git)
    if dep.files:
        inline.append("files", dep.files)
    if dep.tonel:
        inline.append("tonel", dep.tonel)
    if dep.filetree:
        inline.append("filetree", dep.filetree)
    return inline
