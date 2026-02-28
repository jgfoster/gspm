"""Tests for gspm.tonel module — Tonel parser and Topaz generator."""

import pytest
from pathlib import Path

from gspm.tonel import (
    parse_tonel,
    generate_tpz,
    generate_combined_tpz,
    discover_tonel_files,
    determine_load_order,
    transpile_directory,
    _parse_ston,
)
from gspm.errors import TonelError


TONEL_FIXTURES = Path(__file__).parent / "fixtures" / "tonel"


# ---------------------------------------------------------------------------
# STON parsing
# ---------------------------------------------------------------------------


class TestStonParser:
    def test_simple_dict(self):
        result = _parse_ston("{ #name : #MyClass, #superclass : #Object }")
        assert result["name"] == "MyClass"
        assert result["superclass"] == "Object"

    def test_quoted_symbol(self):
        result = _parse_ston("{ #category : #'MyApp-Core' }")
        assert result["category"] == "MyApp-Core"

    def test_string_array(self):
        result = _parse_ston("{ #instVars : [ 'foo', 'bar' ] }")
        assert result["instVars"] == ["foo", "bar"]

    def test_empty_array(self):
        result = _parse_ston("{ #instVars : [] }")
        assert result["instVars"] == []

    def test_paren_array(self):
        result = _parse_ston("{ #options : #() }")
        assert result["options"] == []

    def test_nested_quoted_values(self):
        result = _parse_ston(
            "{ #name : #String, #category : #'*MyApp-Extensions' }"
        )
        assert result["name"] == "String"
        assert result["category"] == "*MyApp-Extensions"


# ---------------------------------------------------------------------------
# Tonel parsing
# ---------------------------------------------------------------------------


class TestParseTonel:
    def test_parse_class(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        assert tc.name == "MyBaseClass"
        assert tc.superclass == "Object"
        assert tc.is_extension is False
        assert "name" in tc.inst_vars
        assert "value" in tc.inst_vars
        assert "DefaultName" in tc.class_vars

    def test_parse_comment(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        assert "base class" in tc.comment

    def test_parse_instance_methods(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        instance_methods = [m for m in tc.methods if not m.is_class_side]
        selectors = [m.selector for m in instance_methods]
        assert "initialize" in selectors
        assert "name" in selectors
        assert "name:" in selectors
        assert "value" in selectors
        assert "value:" in selectors

    def test_parse_class_methods(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        class_methods = [m for m in tc.methods if m.is_class_side]
        selectors = [m.selector for m in class_methods]
        assert "initialize" in selectors
        assert "named:" in selectors

    def test_parse_method_category(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        name_method = next(
            m for m in tc.methods if m.selector == "name" and not m.is_class_side
        )
        assert name_method.category == "accessing"

    def test_parse_method_body(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        name_method = next(
            m for m in tc.methods if m.selector == "name" and not m.is_class_side
        )
        assert "^ name" in name_method.source

    def test_parse_subclass(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MySubClass.st").read_text())
        assert tc.name == "MySubClass"
        assert tc.superclass == "MyBaseClass"
        assert "extra" in tc.inst_vars

    def test_parse_extension(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())
        assert tc.name == "String"
        assert tc.is_extension is True
        assert tc.superclass == ""

    def test_extension_methods(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())
        selectors = [m.selector for m in tc.methods]
        assert "asMyBase" in selectors
        assert "isMyAppString" in selectors

    def test_invalid_file(self):
        with pytest.raises(TonelError):
            parse_tonel("this is not a tonel file")

    def test_missing_name(self):
        with pytest.raises(TonelError, match="Missing #name"):
            parse_tonel("Class { #superclass : #Object }")


# ---------------------------------------------------------------------------
# TPZ generation
# ---------------------------------------------------------------------------


class TestGenerateTpz:
    def test_class_definition(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        tpz = generate_tpz(tc)

        assert "! Class: MyBaseClass" in tpz
        assert "Object subclass: #MyBaseClass" in tpz
        assert "instVarNames: #( name value)" in tpz
        assert "#DefaultName" in tpz

    def test_instance_methods(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        tpz = generate_tpz(tc)

        assert "method: MyBaseClass" in tpz
        assert "^ name" in tpz

    def test_class_methods(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        tpz = generate_tpz(tc)

        assert "classmethod: MyBaseClass" in tpz
        assert "DefaultName := " in tpz

    def test_extension_no_class_def(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())
        tpz = generate_tpz(tc)

        assert "! Extension: String" in tpz
        assert "subclass:" not in tpz
        assert "method: String" in tpz

    def test_method_terminators(self):
        tc = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        tpz = generate_tpz(tc)

        # Each method should end with %
        assert tpz.count("%") >= len(tc.methods) + 1  # +1 for class def


# ---------------------------------------------------------------------------
# Load order
# ---------------------------------------------------------------------------


class TestLoadOrder:
    def test_superclass_before_subclass(self):
        base = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        sub = parse_tonel(TONEL_FIXTURES.joinpath("MySubClass.st").read_text())

        ordered = determine_load_order([sub, base])  # intentionally reversed
        names = [c.name for c in ordered]
        assert names.index("MyBaseClass") < names.index("MySubClass")

    def test_extensions_after_classes(self):
        base = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        ext = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())

        ordered = determine_load_order([ext, base])
        assert not ordered[0].is_extension
        assert ordered[-1].is_extension

    def test_full_order(self):
        base = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        sub = parse_tonel(TONEL_FIXTURES.joinpath("MySubClass.st").read_text())
        ext = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())

        ordered = determine_load_order([ext, sub, base])
        names = [c.name for c in ordered]

        # MyBaseClass before MySubClass, String (extension) last
        assert names.index("MyBaseClass") < names.index("MySubClass")
        assert names[-1] == "String"

    def test_extensions_only(self):
        ext = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())
        ordered = determine_load_order([ext])
        assert len(ordered) == 1
        assert ordered[0].is_extension


# ---------------------------------------------------------------------------
# Directory processing
# ---------------------------------------------------------------------------


class TestDiscoverFiles:
    def test_discover(self):
        files = discover_tonel_files(TONEL_FIXTURES)
        names = [f.name for f in files]
        assert "MyBaseClass.st" in names
        assert "MySubClass.st" in names
        assert "StringExtension.st" in names

    def test_missing_dir(self):
        with pytest.raises(TonelError, match="not found"):
            discover_tonel_files(Path("/nonexistent"))


class TestGenerateCombinedTpz:
    def test_definitions_before_methods(self):
        base = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        sub = parse_tonel(TONEL_FIXTURES.joinpath("MySubClass.st").read_text())
        ext = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())

        ordered = determine_load_order([ext, sub, base])
        tpz = generate_combined_tpz(ordered)

        # Phase markers should exist
        assert "! Phase 1: class definitions" in tpz
        assert "! Phase 2: methods" in tpz

        # All class defs should appear before any method
        phase1_pos = tpz.index("! Phase 1")
        phase2_pos = tpz.index("! Phase 2")

        # Class definitions are in phase 1
        base_def_pos = tpz.index("Object subclass: #MyBaseClass")
        sub_def_pos = tpz.index("MyBaseClass subclass: #MySubClass")
        assert phase1_pos < base_def_pos < phase2_pos
        assert phase1_pos < sub_def_pos < phase2_pos

        # Methods are in phase 2
        method_pos = tpz.index("method: MyBaseClass")
        assert method_pos > phase2_pos

    def test_superclass_def_before_subclass_def(self):
        base = parse_tonel(TONEL_FIXTURES.joinpath("MyBaseClass.st").read_text())
        sub = parse_tonel(TONEL_FIXTURES.joinpath("MySubClass.st").read_text())

        ordered = determine_load_order([sub, base])
        tpz = generate_combined_tpz(ordered)

        base_pos = tpz.index("Object subclass: #MyBaseClass")
        sub_pos = tpz.index("MyBaseClass subclass: #MySubClass")
        assert base_pos < sub_pos

    def test_extension_no_def_in_phase1(self):
        ext = parse_tonel(TONEL_FIXTURES.joinpath("StringExtension.st").read_text())
        tpz = generate_combined_tpz([ext])

        assert "! Extension: String" in tpz
        assert "subclass:" not in tpz


class TestTranspileDirectory:
    def test_transpile(self, tmp_path):
        dest = tmp_path / "output"
        result = transpile_directory(TONEL_FIXTURES, dest)

        # Single combined .tpz file
        assert len(result) == 1
        assert dest.is_dir()

        tpz_path = result[0]
        assert tpz_path.suffix == ".tpz"
        assert tpz_path.exists()
        content = tpz_path.read_text()
        assert "%" in content  # has method terminators

    def test_transpile_two_phase(self, tmp_path):
        dest = tmp_path / "output"
        result = transpile_directory(TONEL_FIXTURES, dest)
        content = result[0].read_text()

        # Definitions come before methods
        assert "! Phase 1: class definitions" in content
        assert "! Phase 2: methods" in content

        phase2_pos = content.index("! Phase 2")
        assert content.index("Object subclass: #MyBaseClass") < phase2_pos
        assert content.index("method: MyBaseClass") > phase2_pos

    def test_transpile_combined_filename(self, tmp_path):
        dest = tmp_path / "output"
        result = transpile_directory(TONEL_FIXTURES, dest)

        # Named after the source directory
        assert result[0].name == "tonel.tpz"

    def test_transpile_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = transpile_directory(empty_dir, tmp_path / "output")
        assert result == []


# ---------------------------------------------------------------------------
# Integration: manifest with tonel
# ---------------------------------------------------------------------------


class TestManifestTonel:
    def test_load_spec_with_tonel(self):
        from gspm.models import LoadSpec
        load = LoadSpec(
            files=["src/bootstrap.gs"],
            tonel=["src/MyPackage"],
        )
        assert load.tonel == ["src/MyPackage"]

    def test_manifest_round_trip_with_tonel(self, tmp_path):
        from gspm.manifest import load_manifest, save_manifest
        from gspm.models import (
            Manifest, PackageMetadata, LoadSpec,
        )

        m = Manifest(
            package=PackageMetadata(name="test", version="1.0.0"),
            load=LoadSpec(
                files=["src/boot.gs"],
                tonel=["src/MyPackage", "src/Other"],
            ),
        )
        path = tmp_path / "gemstone.toml"
        save_manifest(m, path)

        m2 = load_manifest(path)
        assert m2.load.tonel == ["src/MyPackage", "src/Other"]
        assert m2.load.files == ["src/boot.gs"]
