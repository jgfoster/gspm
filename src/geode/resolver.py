"""Dependency version resolution for geode.

Implements a recursive resolver with backtracking. For each dependency,
the highest compatible version is tried first. If transitive dependencies
cause a conflict, the resolver backtracks and tries the next version.
"""

import copy
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tomlkit
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from geode.errors import ResolverError
from geode.models import Dependency, Lockfile, Manifest, ResolvedPackage
from geode.manifest import evaluate_conditional_dependencies, expand_constraint


class PackageSource:
    """Provides version listings and dependency info for packages.

    Uses git operations to discover versions (tags) and read gemstone.toml
    from remote repositories. Can be subclassed/mocked for testing.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        # Lazy import to avoid circular dependency
        from geode import cache, git

        self._git = git
        self._cache = cache

    def available_versions(self, name: str, git_url: str) -> List[Tuple[Version, str]]:
        """Return available (version, sha) pairs, sorted descending by version."""
        bare_path = self._cache.bare_repo_path(self._project_root, name)
        self._cache.ensure_dirs(self._project_root)
        self._git.clone_bare(git_url, bare_path)

        tags = self._git.list_tags(bare_path)
        results: List[Tuple[Version, str]] = []

        for tag in tags:
            version = tag_to_version(tag)
            if version is None:
                continue
            sha = self._git.resolve_ref(bare_path, tag)
            results.append((version, sha))

        results.sort(key=lambda x: x[0], reverse=True)
        return results

    def get_dependencies(
        self, name: str, git_url: str, version: Version, sha: str
    ) -> Dict[str, Dependency]:
        """Get declared dependencies of a specific package version."""
        bare_path = self._cache.bare_repo_path(self._project_root, name)

        try:
            content = self._git.read_file_at_ref(bare_path, sha, "gemstone.toml")
        except Exception:
            # Package has no gemstone.toml — no dependencies
            return {}

        try:
            doc = tomlkit.loads(content)
        except Exception:
            return {}

        deps: Dict[str, Dependency] = {}
        for dep_name, spec in doc.get("dependencies", {}).items():
            if isinstance(spec, str):
                deps[dep_name] = Dependency(name=dep_name, version=spec)
            elif isinstance(spec, dict):
                deps[dep_name] = Dependency(
                    name=dep_name,
                    version=spec.get("version", "*"),
                    git=spec.get("git", ""),
                )

        return deps


class Resolver:
    """Resolve dependency constraints to concrete versions.

    Algorithm:
    1. Start with root manifest's direct dependencies.
    2. For each unresolved dep, try highest compatible version.
    3. Fetch that version's transitive deps and add constraints.
    4. On conflict, backtrack and try next version.
    5. Repeat until all resolved or resolution fails.
    """

    def __init__(self, source: PackageSource) -> None:
        self._source = source

    def resolve(
        self,
        manifest: Manifest,
        include_dev: bool = False,
        gemstone_version: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> Lockfile:
        """Resolve all dependencies and return a Lockfile.

        ``gemstone_version`` and ``platform`` activate matching
        conditional-dependency blocks. When omitted, gemstone-conditional
        and platform-conditional blocks are skipped respectively.
        """
        resolved: Dict[str, Tuple[Version, str, str, List[str]]] = {}
        # name -> (version, sha, git_url, [dep_names])
        constraints: Dict[str, List[SpecifierSet]] = {}

        # Collect root dependencies
        all_deps = dict(manifest.dependencies)
        all_deps.update(evaluate_conditional_dependencies(
            manifest.conditional_dependencies, gemstone_version, platform,
        ))
        if include_dev:
            all_deps.update(manifest.dev_dependencies)
            all_deps.update(evaluate_conditional_dependencies(
                manifest.conditional_dev_dependencies,
                gemstone_version, platform,
            ))

        # Resolve each dependency
        for name, dep in all_deps.items():
            self._resolve_one(name, dep, resolved, constraints, chain=[])

        # Build lockfile
        packages = []
        for name, (version, sha, git_url, dep_names) in resolved.items():
            packages.append(
                ResolvedPackage(
                    name=name,
                    version=str(version),
                    source=f"git+{git_url}",
                    sha=sha,
                    dependencies=dep_names,
                )
            )

        return Lockfile(packages=packages)

    def _resolve_one(
        self,
        name: str,
        dep: Dependency,
        resolved: Dict[str, Tuple[Version, str, str, List[str]]],
        constraints: Dict[str, List[SpecifierSet]],
        chain: List[str],
    ) -> None:
        """Recursively resolve a single package and its transitive deps."""
        # Cycle detection
        if name in chain:
            cycle = " -> ".join(chain + [name])
            raise ResolverError(f"Circular dependency detected: {cycle}")

        # Add constraint from this reference
        spec = SpecifierSet(expand_constraint(dep.version))
        if name not in constraints:
            constraints[name] = []
        constraints[name].append(spec)

        # Already resolved — check compatibility
        if name in resolved:
            existing_version = resolved[name][0]
            if not self._satisfies_all(existing_version, constraints[name]):
                raise ResolverError(
                    f"Version conflict for '{name}': {existing_version} does not "
                    f"satisfy all constraints {[str(s) for s in constraints[name]]}"
                )
            return

        # Get available versions
        git_url = dep.git
        if not git_url:
            raise ResolverError(
                f"No git URL for dependency '{name}'. "
                "Specify a git URL or configure a registry."
            )

        versions = self._source.available_versions(name, git_url)
        if not versions:
            raise ResolverError(f"No versions found for '{name}' at {git_url}")

        # Try each version, highest first
        errors: List[str] = []
        for version, sha in versions:
            if not self._satisfies_all(version, constraints[name]):
                continue

            # Speculatively resolve transitive deps
            saved_resolved = copy.deepcopy(resolved)
            saved_constraints = copy.deepcopy(constraints)

            try:
                transitive = self._source.get_dependencies(
                    name, git_url, version, sha
                )

                # Register this resolution
                resolved[name] = (version, sha, git_url, list(transitive.keys()))

                # Resolve transitive deps
                for tdep_name, tdep in transitive.items():
                    # Inherit git URL from registry/parent if not specified
                    if not tdep.git:
                        tdep = Dependency(
                            name=tdep.name, version=tdep.version, git=tdep.git
                        )
                    self._resolve_one(
                        tdep_name, tdep, resolved, constraints,
                        chain=chain + [name],
                    )

                return  # Success

            except ResolverError as e:
                # Backtrack
                resolved.clear()
                resolved.update(saved_resolved)
                constraints.clear()
                constraints.update(saved_constraints)
                errors.append(f"  {version}: {e}")

        # No version worked
        constraint_strs = [str(s) for s in constraints.get(name, [])]
        raise ResolverError(
            f"No compatible version of '{name}' found.\n"
            f"Constraints: {constraint_strs}\n"
            f"Tried:\n" + "\n".join(errors) if errors else
            f"No versions satisfy {constraint_strs}"
        )

    def _satisfies_all(
        self, version: Version, specs: List[SpecifierSet]
    ) -> bool:
        """Check if a version satisfies all constraints."""
        return all(version in spec for spec in specs)


def tag_to_version(tag: str) -> Optional[Version]:
    """Parse a git tag into a Version, stripping optional 'v' prefix."""
    tag = tag.strip()
    if tag.startswith("v"):
        tag = tag[1:]
    try:
        return Version(tag)
    except InvalidVersion:
        return None
