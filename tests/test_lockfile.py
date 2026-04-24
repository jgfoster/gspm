"""Tests for geode.lockfile module."""

import pytest
from pathlib import Path

from geode.lockfile import load_lockfile, save_lockfile
from geode.models import Lockfile, ResolvedPackage
from geode.errors import LockfileError


class TestLoadLockfile:
    """Test gemstone.lock parsing."""

    def test_load_sample(self, sample_lockfile_path):
        lf = load_lockfile(sample_lockfile_path)
        assert len(lf.packages) == 3

    def test_package_fields(self, sample_lockfile_path):
        lf = load_lockfile(sample_lockfile_path)
        zinc = lf.find("zinc")
        assert zinc is not None
        assert zinc.version == "1.3.1"
        assert zinc.source == "git+https://github.com/svenvc/zinc"
        assert zinc.sha == "b84c1f209d3e5a"

    def test_dependencies(self, sample_lockfile_path):
        lf = load_lockfile(sample_lockfile_path)
        magritte = lf.find("magritte")
        assert magritte is not None
        assert "zinc" in magritte.dependencies

    def test_missing_file_returns_empty(self, tmp_path):
        lf = load_lockfile(tmp_path / "nonexistent.lock")
        assert len(lf.packages) == 0

    def test_find_missing_returns_none(self, sample_lockfile_path):
        lf = load_lockfile(sample_lockfile_path)
        assert lf.find("nonexistent") is None


class TestSaveLockfile:
    """Test gemstone.lock writing."""

    def test_round_trip(self, tmp_path):
        lockfile = Lockfile(packages=[
            ResolvedPackage(
                name="zinc",
                version="1.3.1",
                source="git+https://github.com/svenvc/zinc",
                sha="b84c1f209d3e5a",
            ),
            ResolvedPackage(
                name="magritte",
                version="2.1.3",
                source="git+https://github.com/magritte-metamodel/magritte",
                sha="f92b3a71cc04d8",
                dependencies=["zinc"],
            ),
        ])

        out = tmp_path / "gemstone.lock"
        save_lockfile(lockfile, out)

        lf2 = load_lockfile(out)
        assert len(lf2.packages) == 2
        assert lf2.find("zinc") is not None
        assert lf2.find("magritte").dependencies == ["zinc"]

    def test_output_has_header(self, tmp_path):
        lockfile = Lockfile(packages=[
            ResolvedPackage(
                name="test",
                version="1.0.0",
                source="git+https://example.com/test",
                sha="abc123",
            ),
        ])

        out = tmp_path / "gemstone.lock"
        save_lockfile(lockfile, out)

        content = out.read_text()
        assert "automatically generated" in content
        assert "Do not edit" in content
