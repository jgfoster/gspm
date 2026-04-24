"""Shared test fixtures for geode."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_manifest_path(fixtures_dir):
    return fixtures_dir / "sample_gemstone.toml"


@pytest.fixture
def sample_lockfile_path(fixtures_dir):
    return fixtures_dir / "sample_gemstone.lock"


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with a skeleton manifest."""
    from geode.manifest import scaffold_manifest

    project = tmp_path / "testproject"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "gemstone.toml").write_text(scaffold_manifest("testproject"))
    return project
