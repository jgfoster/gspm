"""Tests for geode.mcz — Monticello .mcz migration shim."""

import zipfile
from pathlib import Path

import pytest

from geode.errors import MczError
from geode.manifest import load_manifest
from geode.mcz import (
    _clean_chunk_source,
    _name_from_filename,
    _normalize_name,
    _parse_package_name,
    migrate_mcz,
)


SAMPLE_SOURCE = """\
Object subclass: #ZnRequest
    instanceVariableNames: 'url method headers'
    classVariableNames: ''
    poolDictionaries: ''
    category: 'Zinc-HTTP'!

!ZnRequest methodsFor: 'accessing' stamp: 'sven 1/2/2024 12:00'!
url
    ^ url! !

!ZnRequest methodsFor: 'accessing' stamp: 'sven 1/2/2024 12:01'!
url: aString
    url := aString! !
"""


def _make_mcz(path: Path, source: str = SAMPLE_SOURCE,
              package_name: str = "Zinc-HTTP") -> Path:
    """Build a minimal .mcz archive with the given source and package name."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("snapshot/source.st", source)
        zf.writestr("package", f"(name '{package_name}')")
    return path


class TestParsePackageName:
    def test_extracts_name(self):
        assert _parse_package_name("(name 'MyPkg')") == "MyPkg"

    def test_handles_whitespace(self):
        assert _parse_package_name("(\n  name 'Foo-Bar'\n)") == "Foo-Bar"

    def test_returns_none_when_missing(self):
        assert _parse_package_name("(other 'thing')") is None


class TestNameFromFilename:
    def test_strips_author_version(self):
        assert _name_from_filename("Zinc-HTTP-sven.42") == "Zinc-HTTP"

    def test_keeps_plain_name(self):
        assert _name_from_filename("PlainName") == "PlainName"

    def test_no_version_means_no_strip(self):
        assert _name_from_filename("Zinc-HTTP") == "Zinc-HTTP"


class TestNormalizeName:
    def test_camel_case(self):
        assert _normalize_name("MyPackage") == "my-package"

    def test_acronym(self):
        assert _normalize_name("ZnHTTPRequest") == "zn-httprequest"

    def test_already_hyphenated(self):
        assert _normalize_name("Zinc-HTTP") == "zinc--http"


class TestCleanChunkSource:
    def test_removes_stamp(self):
        text = "!Foo methodsFor: 'cat' stamp: 'a 1/2/3'!"
        assert "stamp:" not in _clean_chunk_source(text)
        assert "methodsFor: 'cat'!" in _clean_chunk_source(text)

    def test_removes_comment_stamp(self):
        text = "Foo commentStamp: 'author' prior: 0"
        cleaned = _clean_chunk_source(text)
        assert "commentStamp:" not in cleaned
        assert "prior:" not in cleaned

    def test_preserves_unstamped(self):
        text = "!Foo methodsFor: 'cat'!\n^ 42! !"
        assert _clean_chunk_source(text) == text


class TestMigrateMcz:
    def test_produces_manifest_and_source(self, tmp_path):
        mcz = _make_mcz(tmp_path / "Zinc-HTTP-sven.42.mcz")
        out = tmp_path / "out"

        manifest_path = migrate_mcz(mcz, out)

        assert manifest_path.exists()
        assert (out / "src" / "Zinc-HTTP.gs").exists()

    def test_manifest_loads_correctly(self, tmp_path):
        mcz = _make_mcz(tmp_path / "MyPkg-author.1.mcz", package_name="MyPackage")
        out = tmp_path / "out"

        migrate_mcz(mcz, out)
        m = load_manifest(out / "gemstone.toml")

        assert m.package.name == "my-package"
        assert m.load.files == ["src/MyPackage.gs"]

    def test_source_has_stamps_stripped(self, tmp_path):
        mcz = _make_mcz(tmp_path / "Zinc-HTTP.mcz")
        out = tmp_path / "out"
        migrate_mcz(mcz, out)

        gs = (out / "src" / "Zinc-HTTP.gs").read_text()
        assert "stamp:" not in gs
        assert "url" in gs
        assert "ZnRequest" in gs

    def test_falls_back_to_filename_without_package_metadata(self, tmp_path):
        mcz_path = tmp_path / "FallbackPkg-author.7.mcz"
        with zipfile.ZipFile(mcz_path, "w") as zf:
            zf.writestr("snapshot/source.st", SAMPLE_SOURCE)
            # No `package` file
        out = tmp_path / "out"
        migrate_mcz(mcz_path, out)

        # Falls back to the filename stem (with -author.N stripped)
        assert (out / "src" / "FallbackPkg.gs").exists()

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(MczError, match="not found"):
            migrate_mcz(tmp_path / "nope.mcz", tmp_path / "out")

    def test_non_zip_raises(self, tmp_path):
        bad = tmp_path / "fake.mcz"
        bad.write_text("not a zip")
        with pytest.raises(MczError, match="valid .mcz"):
            migrate_mcz(bad, tmp_path / "out")

    def test_no_source_raises(self, tmp_path):
        mcz_path = tmp_path / "empty.mcz"
        with zipfile.ZipFile(mcz_path, "w") as zf:
            zf.writestr("package", "(name 'Empty')")
        with pytest.raises(MczError, match="No source.st"):
            migrate_mcz(mcz_path, tmp_path / "out")
