"""Tests for gspm.manifest module."""

import pytest
from pathlib import Path

from gspm.manifest import (
    expand_constraint,
    load_manifest,
    save_manifest,
    add_dependency,
    scaffold_manifest,
)
from gspm.errors import ManifestError


class TestExpandConstraint:
    """Test Cargo-style constraint to PEP 440 conversion."""

    def test_caret_major(self):
        assert expand_constraint("^1.2.3") == ">=1.2.3,<2.0.0"

    def test_caret_minor(self):
        assert expand_constraint("^0.2.3") == ">=0.2.3,<0.3.0"

    def test_caret_patch(self):
        assert expand_constraint("^0.0.3") == ">=0.0.3,<0.0.4"

    def test_caret_two_part(self):
        assert expand_constraint("^1.2") == ">=1.2,<2.0.0"

    def test_caret_one_part(self):
        assert expand_constraint("^2") == ">=2,<3.0.0"

    def test_tilde(self):
        assert expand_constraint("~1.2.3") == ">=1.2.3,<1.3.0"

    def test_tilde_two_part(self):
        assert expand_constraint("~1.2") == ">=1.2,<1.3.0"

    def test_wildcard(self):
        assert expand_constraint("*") == ">=0"

    def test_pep440_passthrough(self):
        assert expand_constraint(">=3.5") == ">=3.5"

    def test_pep440_range_passthrough(self):
        assert expand_constraint(">=1.0,<2.0") == ">=1.0,<2.0"

    def test_invalid_raises(self):
        with pytest.raises(ManifestError):
            expand_constraint("not-a-version")


class TestLoadManifest:
    """Test gemstone.toml parsing."""

    def test_load_sample(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert m.package.name == "seaside"
        assert m.package.version == "3.5.0"
        assert m.package.description == "Web application framework for GemStone"
        assert m.package.gemstone == ">=3.5"
        assert m.package.license == "MIT"
        assert "Seaside Team" in m.package.authors

    def test_load_files(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert len(m.load.files) == 4
        assert m.load.files[0] == "src/core/SeasideCore.gs"

    def test_load_conditions(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert ">=3.7" in m.load.conditions
        assert ">=3.6,<3.7" in m.load.conditions

    def test_dependencies(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert "magritte" in m.dependencies
        assert m.dependencies["magritte"].version == "^2.0"
        assert "github.com" in m.dependencies["magritte"].git

    def test_dev_dependencies(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert "sunit" in m.dev_dependencies

    def test_test_files(self, sample_manifest_path):
        m = load_manifest(sample_manifest_path)
        assert m.test.files == ["tests/SeasideTests.gs"]

    def test_missing_file(self, tmp_path):
        with pytest.raises(ManifestError, match="not found"):
            load_manifest(tmp_path / "nonexistent.toml")

    def test_missing_package_section(self, tmp_path):
        f = tmp_path / "gemstone.toml"
        f.write_text("[load]\nfiles = []\n")
        with pytest.raises(ManifestError, match="Missing \\[package\\]"):
            load_manifest(f)

    def test_missing_name(self, tmp_path):
        f = tmp_path / "gemstone.toml"
        f.write_text('[package]\nversion = "1.0"\n')
        with pytest.raises(ManifestError, match="package.name"):
            load_manifest(f)


class TestSaveManifest:
    """Test gemstone.toml writing."""

    def test_round_trip(self, sample_manifest_path, tmp_path):
        m = load_manifest(sample_manifest_path)
        out = tmp_path / "gemstone.toml"
        save_manifest(m, out)

        m2 = load_manifest(out)
        assert m2.package.name == m.package.name
        assert m2.package.version == m.package.version
        assert len(m2.load.files) == len(m.load.files)
        assert set(m2.dependencies.keys()) == set(m.dependencies.keys())

    def test_round_trip_with_dep_overrides(self, tmp_path):
        from gspm.models import Manifest, PackageMetadata, Dependency

        m = Manifest(
            package=PackageMetadata(name="test", version="1.0.0"),
            dependencies={
                "seaside": Dependency(
                    name="seaside",
                    version="^3.5",
                    git="https://example.com/seaside",
                    tonel=["src/Seaside-Core"],
                ),
                "zinc": Dependency(
                    name="zinc",
                    version="^1.2",
                    git="https://example.com/zinc",
                    files=["src/ZnCore.gs"],
                ),
            },
        )
        out = tmp_path / "gemstone.toml"
        save_manifest(m, out)

        m2 = load_manifest(out)
        assert m2.dependencies["seaside"].tonel == ["src/Seaside-Core"]
        assert m2.dependencies["zinc"].files == ["src/ZnCore.gs"]

    def test_round_trip_with_filetree_override(self, tmp_path):
        from gspm.models import Manifest, PackageMetadata, Dependency

        m = Manifest(
            package=PackageMetadata(name="test", version="1.0.0"),
            dependencies={
                "grease": Dependency(
                    name="grease",
                    version="^1.0",
                    git="https://example.com/grease",
                    filetree=["repository/Grease-Core.package"],
                ),
            },
        )
        out = tmp_path / "gemstone.toml"
        save_manifest(m, out)

        m2 = load_manifest(out)
        assert m2.dependencies["grease"].filetree == ["repository/Grease-Core.package"]


class TestAddDependency:
    """Test adding dependencies to gemstone.toml."""

    def test_add_dependency(self, tmp_project):
        manifest_path = tmp_project / "gemstone.toml"
        add_dependency(manifest_path, "grease", "^1.0", git="https://example.com/grease")

        m = load_manifest(manifest_path)
        assert "grease" in m.dependencies
        assert m.dependencies["grease"].version == "^1.0"
        assert m.dependencies["grease"].git == "https://example.com/grease"

    def test_add_dev_dependency(self, tmp_project):
        manifest_path = tmp_project / "gemstone.toml"
        add_dependency(manifest_path, "sunit", "^1.0", git="https://example.com/sunit", dev=True)

        m = load_manifest(manifest_path)
        assert "sunit" in m.dev_dependencies

    def test_add_with_tonel_override(self, tmp_project):
        manifest_path = tmp_project / "gemstone.toml"
        add_dependency(
            manifest_path, "seaside", "^3.5",
            git="https://example.com/seaside",
            tonel=["src/Seaside-Core", "src/Seaside-Adaptors"],
        )

        m = load_manifest(manifest_path)
        assert m.dependencies["seaside"].tonel == ["src/Seaside-Core", "src/Seaside-Adaptors"]

    def test_add_with_files_override(self, tmp_project):
        manifest_path = tmp_project / "gemstone.toml"
        add_dependency(
            manifest_path, "zinc", "^1.2",
            git="https://example.com/zinc",
            files=["src/ZnCore.gs", "src/ZnClient.gs"],
        )

        m = load_manifest(manifest_path)
        assert m.dependencies["zinc"].files == ["src/ZnCore.gs", "src/ZnClient.gs"]

    def test_add_with_filetree_override(self, tmp_project):
        manifest_path = tmp_project / "gemstone.toml"
        add_dependency(
            manifest_path, "grease", "^1.0",
            git="https://example.com/grease",
            filetree=["repository/Grease-Core.package", "repository/Grease-GemStone-Core.package"],
        )

        m = load_manifest(manifest_path)
        assert m.dependencies["grease"].filetree == [
            "repository/Grease-Core.package",
            "repository/Grease-GemStone-Core.package",
        ]


class TestScaffoldManifest:
    """Test skeleton manifest generation."""

    def test_scaffold_has_package(self):
        content = scaffold_manifest("myapp")
        assert 'name = "myapp"' in content
        assert 'version = "0.1.0"' in content

    def test_scaffold_has_load(self):
        content = scaffold_manifest("myapp")
        assert "src/myapp.gs" in content

    def test_scaffold_is_valid_toml(self, tmp_path):
        f = tmp_path / "gemstone.toml"
        f.write_text(scaffold_manifest("myapp"))
        m = load_manifest(f)
        assert m.package.name == "myapp"
