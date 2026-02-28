"""Integration tests for gspm CLI."""

import pytest
from pathlib import Path

from click.testing import CliRunner

from gspm.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestVersion:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestInit:
    def test_init_creates_project(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "myproject"])
            assert result.exit_code == 0
            assert "Created" in result.output
            assert Path("myproject/gemstone.toml").exists()
            assert Path("myproject/src").is_dir()
            assert Path("myproject/tests").is_dir()

    def test_init_in_current_dir(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path("gemstone.toml").exists()

    def test_init_existing_manifest(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("gemstone.toml").write_text("[package]\nname = 'x'\nversion = '1.0'\n")
            result = runner.invoke(main, ["init"])
            assert "already exists" in result.output


class TestTree:
    def test_tree_no_lockfile(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["tree"])
            assert result.exit_code != 0

    def test_tree_with_lockfile(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Copy sample lockfile
            import shutil
            fixtures = Path(__file__).parent / "fixtures"
            shutil.copy(fixtures / "sample_gemstone.lock", "gemstone.lock")

            result = runner.invoke(main, ["tree"])
            assert result.exit_code == 0
            assert "zinc" in result.output
            assert "magritte" in result.output
            assert "seaside" in result.output


class TestInstallDryRun:
    def test_dry_run_shows_script(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create minimal project
            Path("gemstone.toml").write_text(
                '[package]\nname = "test"\nversion = "1.0.0"\n\n'
                '[load]\nfiles = ["src/Test.gs"]\n'
            )
            Path("gemstone.lock").write_text("")

            result = runner.invoke(main, ["install", "--dry-run", "mystone"])
            assert result.exit_code == 0
            assert "set gemstone mystone" in result.output
            assert "login" in result.output
            assert "commit" in result.output
