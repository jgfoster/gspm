"""Tests for gspm.resolver module."""

import pytest
from typing import Dict, List, Tuple

from packaging.version import Version

from gspm.errors import ResolverError
from gspm.models import (
    ConditionalDeps,
    Dependency,
    Manifest,
    PackageMetadata,
    LoadSpec,
    SuiteSpec,
)
from gspm.resolver import Resolver, tag_to_version


class MockPackageSource:
    """Mock PackageSource that returns canned data for testing.

    registry maps package_name -> [(version_str, sha, {dep_name: dep_spec})]
    """

    def __init__(self, registry: Dict[str, List[Tuple[str, str, Dict[str, str]]]]):
        self._registry = registry

    def available_versions(self, name: str, git_url: str) -> List[Tuple[Version, str]]:
        if name not in self._registry:
            return []
        results = []
        for version_str, sha, _ in self._registry[name]:
            results.append((Version(version_str), sha))
        results.sort(key=lambda x: x[0], reverse=True)
        return results

    def get_dependencies(
        self, name: str, git_url: str, version: Version, sha: str
    ) -> Dict[str, Dependency]:
        if name not in self._registry:
            return {}
        for version_str, entry_sha, deps in self._registry[name]:
            if entry_sha == sha:
                return {
                    dep_name: Dependency(
                        name=dep_name,
                        version=dep_spec,
                        git=f"https://example.com/{dep_name}",
                    )
                    for dep_name, dep_spec in deps.items()
                }
        return {}


def _make_manifest(**deps) -> Manifest:
    """Create a minimal Manifest with the given dependencies."""
    return Manifest(
        package=PackageMetadata(name="root", version="1.0.0"),
        dependencies={
            name: Dependency(
                name=name,
                version=spec,
                git=f"https://example.com/{name}",
            )
            for name, spec in deps.items()
        },
    )


class TestTagToVersion:
    def test_plain_version(self):
        assert tag_to_version("1.2.3") == Version("1.2.3")

    def test_v_prefix(self):
        assert tag_to_version("v1.2.3") == Version("1.2.3")

    def test_invalid(self):
        assert tag_to_version("not-a-version") is None

    def test_whitespace(self):
        assert tag_to_version("  v2.0.0  ") == Version("2.0.0")


class TestResolver:
    """Test dependency resolution."""

    def test_simple_single_dep(self):
        """A depends on B. B has one version."""
        source = MockPackageSource({
            "b": [("1.0.0", "sha-b-100", {})],
        })
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)
        lockfile = resolver.resolve(manifest)

        assert len(lockfile.packages) == 1
        assert lockfile.find("b").version == "1.0.0"

    def test_transitive_deps(self):
        """A -> B -> C. All resolve cleanly."""
        source = MockPackageSource({
            "b": [("1.0.0", "sha-b-100", {"c": "^1.0"})],
            "c": [("1.2.0", "sha-c-120", {})],
        })
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)
        lockfile = resolver.resolve(manifest)

        assert len(lockfile.packages) == 2
        assert lockfile.find("b") is not None
        assert lockfile.find("c") is not None

    def test_picks_highest_version(self):
        """Resolver should pick the highest compatible version."""
        source = MockPackageSource({
            "b": [
                ("1.0.0", "sha-b-100", {}),
                ("1.1.0", "sha-b-110", {}),
                ("1.2.0", "sha-b-120", {}),
            ],
        })
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)
        lockfile = resolver.resolve(manifest)

        assert lockfile.find("b").version == "1.2.0"

    def test_diamond_dependency(self):
        """A depends on B and C. Both B and C depend on D."""
        source = MockPackageSource({
            "b": [("1.0.0", "sha-b-100", {"d": "^1.0"})],
            "c": [("1.0.0", "sha-c-100", {"d": "^1.0"})],
            "d": [("1.5.0", "sha-d-150", {})],
        })
        manifest = _make_manifest(b="^1.0", c="^1.0")
        resolver = Resolver(source)
        lockfile = resolver.resolve(manifest)

        assert len(lockfile.packages) == 3
        assert lockfile.find("d").version == "1.5.0"

    def test_version_conflict_raises(self):
        """B requires D ^1.0, C requires D ^2.0. Irreconcilable."""
        source = MockPackageSource({
            "b": [("1.0.0", "sha-b-100", {"d": "^1.0"})],
            "c": [("1.0.0", "sha-c-100", {"d": "^2.0"})],
            "d": [
                ("1.5.0", "sha-d-150", {}),
                ("2.0.0", "sha-d-200", {}),
            ],
        })
        manifest = _make_manifest(b="^1.0", c="^1.0")
        resolver = Resolver(source)

        with pytest.raises(ResolverError):
            resolver.resolve(manifest)

    def test_backtracking(self):
        """B 1.5 needs C ^2.0 (unavailable). B 1.4 needs C ^1.0 (available)."""
        source = MockPackageSource({
            "b": [
                ("1.5.0", "sha-b-150", {"c": "^2.0"}),
                ("1.4.0", "sha-b-140", {"c": "^1.0"}),
            ],
            "c": [("1.0.0", "sha-c-100", {})],
        })
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)
        lockfile = resolver.resolve(manifest)

        assert lockfile.find("b").version == "1.4.0"
        assert lockfile.find("c").version == "1.0.0"

    def test_no_versions_raises(self):
        """Package exists but no versions match."""
        source = MockPackageSource({
            "b": [("2.0.0", "sha-b-200", {})],
        })
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)

        with pytest.raises(ResolverError):
            resolver.resolve(manifest)

    def test_missing_package_raises(self):
        """Package not found at all."""
        source = MockPackageSource({})
        manifest = _make_manifest(b="^1.0")
        resolver = Resolver(source)

        with pytest.raises(ResolverError):
            resolver.resolve(manifest)

    def test_dev_dependencies(self):
        """Dev deps are included when include_dev=True."""
        source = MockPackageSource({
            "b": [("1.0.0", "sha-b-100", {})],
            "testlib": [("1.0.0", "sha-tl-100", {})],
        })
        manifest = Manifest(
            package=PackageMetadata(name="root", version="1.0.0"),
            dependencies={
                "b": Dependency(name="b", version="^1.0", git="https://example.com/b"),
            },
            dev_dependencies={
                "testlib": Dependency(
                    name="testlib", version="^1.0", git="https://example.com/testlib"
                ),
            },
        )
        resolver = Resolver(source)

        # Without dev deps
        lockfile = resolver.resolve(manifest, include_dev=False)
        assert lockfile.find("testlib") is None

        # With dev deps
        lockfile_dev = resolver.resolve(manifest, include_dev=True)
        assert lockfile_dev.find("testlib") is not None


class TestConditionalDependencies:
    """Test that the resolver activates the right conditional blocks."""

    def _registry(self):
        return MockPackageSource({
            "core":   [("1.0.0", "sha-core", {})],
            "gs37":   [("1.0.0", "sha-gs37", {})],
            "linux":  [("1.0.0", "sha-linux", {})],
            "darwin": [("1.0.0", "sha-darwin", {})],
        })

    def _make_manifest(self):
        return Manifest(
            package=PackageMetadata(name="root", version="1.0.0"),
            dependencies={
                "core": Dependency(name="core", version="^1.0",
                                   git="https://example.com/core"),
            },
            conditional_dependencies=[
                ConditionalDeps(
                    dimension="gemstone", spec=">=3.7",
                    deps={"gs37": Dependency(name="gs37", version="^1.0",
                                              git="https://example.com/gs37")},
                ),
                ConditionalDeps(
                    dimension="platform", spec="linux",
                    deps={"linux": Dependency(name="linux", version="^1.0",
                                               git="https://example.com/linux")},
                ),
                ConditionalDeps(
                    dimension="platform", spec="macos",
                    deps={"darwin": Dependency(name="darwin", version="^1.0",
                                                git="https://example.com/darwin")},
                ),
            ],
        )

    def test_no_environment_skips_conditionals(self):
        resolver = Resolver(self._registry())
        lockfile = resolver.resolve(self._make_manifest())
        assert lockfile.find("core") is not None
        assert lockfile.find("gs37") is None
        assert lockfile.find("linux") is None
        assert lockfile.find("darwin") is None

    def test_gemstone_version_activates_block(self):
        resolver = Resolver(self._registry())
        lockfile = resolver.resolve(
            self._make_manifest(), gemstone_version="3.7.0"
        )
        assert lockfile.find("gs37") is not None
        # Old version: no activation
        lockfile2 = resolver.resolve(
            self._make_manifest(), gemstone_version="3.6.0"
        )
        assert lockfile2.find("gs37") is None

    def test_platform_activates_correct_block(self):
        resolver = Resolver(self._registry())
        lf_linux = resolver.resolve(self._make_manifest(), platform="linux")
        assert lf_linux.find("linux") is not None
        assert lf_linux.find("darwin") is None

        lf_macos = resolver.resolve(self._make_manifest(), platform="macos")
        assert lf_macos.find("darwin") is not None
        assert lf_macos.find("linux") is None

    def test_combined_activation(self):
        resolver = Resolver(self._registry())
        lockfile = resolver.resolve(
            self._make_manifest(),
            gemstone_version="3.7.5",
            platform="linux",
        )
        assert lockfile.find("core") is not None
        assert lockfile.find("gs37") is not None
        assert lockfile.find("linux") is not None
        assert lockfile.find("darwin") is None
