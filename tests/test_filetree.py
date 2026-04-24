"""Tests for geode.filetree module — FileTree parser and Topaz generator."""

import pytest
from pathlib import Path

from geode.filetree import (
    parse_filetree_method,
    parse_filetree_class,
    parse_filetree_extension,
    parse_filetree_package,
    discover_filetree_packages,
    transpile_filetree_package,
)
from geode.errors import FileTreeError


FILETREE_FIXTURES = Path(__file__).parent / "fixtures" / "filetree"
PACKAGE_DIR = FILETREE_FIXTURES / "TestPkg.package"


class TestParseMethod:
    """Test parsing individual FileTree method .st files."""

    def test_instance_method(self):
        method_path = PACKAGE_DIR / "MyBaseClass.class" / "instance" / "name.st"
        m = parse_filetree_method(method_path, is_class_side=False)
        assert m.selector == "name"
        assert m.category == "accessing"
        assert not m.is_class_side
        assert "^ name" in m.source

    def test_class_method(self):
        method_path = PACKAGE_DIR / "MyBaseClass.class" / "class" / "named..st"
        m = parse_filetree_method(method_path, is_class_side=True)
        assert m.selector == "named:"
        assert m.category == "instance creation"
        assert m.is_class_side

    def test_keyword_setter(self):
        method_path = PACKAGE_DIR / "MyBaseClass.class" / "instance" / "name..st"
        m = parse_filetree_method(method_path, is_class_side=False)
        assert m.selector == "name:"
        assert "name := aString" in m.source

    def test_extension_category(self):
        method_path = PACKAGE_DIR / "String.extension" / "instance" / "asMyBase.st"
        m = parse_filetree_method(method_path, is_class_side=False)
        assert m.category == "*TestPkg"
        assert m.selector == "asMyBase"

    def test_empty_method_file_raises(self, tmp_path):
        f = tmp_path / "bad.st"
        f.write_text("accessing\n")
        with pytest.raises(FileTreeError, match="too short"):
            parse_filetree_method(f, is_class_side=False)


class TestParseClass:
    """Test parsing .class/ directories."""

    def test_class_properties(self):
        class_dir = PACKAGE_DIR / "MyBaseClass.class"
        tc = parse_filetree_class(class_dir)
        assert tc.name == "MyBaseClass"
        assert tc.superclass == "Object"
        assert tc.inst_vars == ["name", "value"]
        assert tc.class_vars == ["DefaultName"]
        assert tc.category == "TestPkg-Core"
        assert not tc.is_extension

    def test_class_comment(self):
        class_dir = PACKAGE_DIR / "MyBaseClass.class"
        tc = parse_filetree_class(class_dir)
        assert tc.comment == "A simple base class for testing."

    def test_class_type(self):
        class_dir = PACKAGE_DIR / "MyBaseClass.class"
        tc = parse_filetree_class(class_dir)
        assert tc.class_type == "normal"

    def test_instance_methods(self):
        class_dir = PACKAGE_DIR / "MyBaseClass.class"
        tc = parse_filetree_class(class_dir)
        instance_methods = [m for m in tc.methods if not m.is_class_side]
        selectors = [m.selector for m in instance_methods]
        assert "name" in selectors
        assert "name:" in selectors
        assert "value" in selectors

    def test_class_methods(self):
        class_dir = PACKAGE_DIR / "MyBaseClass.class"
        tc = parse_filetree_class(class_dir)
        class_methods = [m for m in tc.methods if m.is_class_side]
        assert len(class_methods) == 1
        assert class_methods[0].selector == "named:"

    def test_subclass(self):
        class_dir = PACKAGE_DIR / "MySubClass.class"
        tc = parse_filetree_class(class_dir)
        assert tc.name == "MySubClass"
        assert tc.superclass == "MyBaseClass"
        assert tc.inst_vars == ["extra"]

    def test_missing_properties_raises(self, tmp_path):
        d = tmp_path / "Bad.class"
        d.mkdir()
        with pytest.raises(FileTreeError, match="Missing properties.json"):
            parse_filetree_class(d)

    def test_variable_type(self, tmp_path):
        d = tmp_path / "VarClass.class"
        d.mkdir()
        (d / "properties.json").write_text(
            '{"name":"VarClass","super":"Object","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"Test","type":"variable"}'
        )
        tc = parse_filetree_class(d)
        assert tc.class_type == "variable"


class TestParseExtension:
    """Test parsing .extension/ directories."""

    def test_extension_is_extension(self):
        ext_dir = PACKAGE_DIR / "String.extension"
        tc = parse_filetree_extension(ext_dir)
        assert tc.is_extension
        assert tc.name == "String"

    def test_extension_no_superclass(self):
        ext_dir = PACKAGE_DIR / "String.extension"
        tc = parse_filetree_extension(ext_dir)
        assert tc.superclass == ""

    def test_extension_methods(self):
        ext_dir = PACKAGE_DIR / "String.extension"
        tc = parse_filetree_extension(ext_dir)
        assert len(tc.methods) == 1
        assert tc.methods[0].selector == "asMyBase"


class TestParsePackage:
    """Test parsing .package/ directories."""

    def test_all_classes_found(self):
        classes = parse_filetree_package(PACKAGE_DIR)
        names = [c.name for c in classes]
        assert "MyBaseClass" in names
        assert "MySubClass" in names
        assert "String" in names

    def test_class_and_extension_count(self):
        classes = parse_filetree_package(PACKAGE_DIR)
        regular = [c for c in classes if not c.is_extension]
        extensions = [c for c in classes if c.is_extension]
        assert len(regular) == 2
        assert len(extensions) == 1

    def test_missing_package_raises(self, tmp_path):
        with pytest.raises(FileTreeError, match="not found"):
            parse_filetree_package(tmp_path / "NonExistent.package")

    def test_empty_package(self, tmp_path):
        d = tmp_path / "Empty.package"
        d.mkdir()
        classes = parse_filetree_package(d)
        assert classes == []


class TestDiscoverPackages:
    """Test .package/ directory discovery."""

    def test_discover(self):
        packages = discover_filetree_packages(FILETREE_FIXTURES)
        names = [p.name for p in packages]
        assert "TestPkg.package" in names

    def test_missing_dir(self):
        packages = discover_filetree_packages(Path("/nonexistent"))
        assert packages == []


class TestTranspilePackage:
    """Test end-to-end FileTree transpilation."""

    def test_transpile(self):
        result = transpile_filetree_package(
            PACKAGE_DIR, FILETREE_FIXTURES.parent.parent / "tmp_ft_output"
        )
        assert len(result) == 1
        assert result[0].suffix == ".tpz"
        # Clean up
        result[0].unlink()
        result[0].parent.rmdir()

    def test_transpile_to_tmp(self, tmp_path):
        result = transpile_filetree_package(PACKAGE_DIR, tmp_path / "output")
        assert len(result) == 1
        content = result[0].read_text()
        assert "Phase 1: class definitions" in content
        assert "Phase 2: methods" in content

    def test_transpile_load_order(self, tmp_path):
        result = transpile_filetree_package(PACKAGE_DIR, tmp_path / "output")
        content = result[0].read_text()
        # MyBaseClass must come before MySubClass
        assert content.index("MyBaseClass") < content.index("MySubClass")

    def test_transpile_filename(self, tmp_path):
        result = transpile_filetree_package(PACKAGE_DIR, tmp_path / "output")
        assert result[0].name == "TestPkg.tpz"

    def test_transpile_empty(self, tmp_path):
        d = tmp_path / "Empty.package"
        d.mkdir()
        result = transpile_filetree_package(d, tmp_path / "output")
        assert result == []

    def test_variable_class_generates_indexable(self, tmp_path):
        """Variable-type class generates indexableSubclass: in .tpz."""
        pkg_dir = tmp_path / "Var.package"
        cls_dir = pkg_dir / "VarArray.class"
        cls_dir.mkdir(parents=True)
        (cls_dir / "properties.json").write_text(
            '{"name":"VarArray","super":"Object","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"Test","type":"variable"}'
        )
        (cls_dir / "README.md").write_text("")
        result = transpile_filetree_package(pkg_dir, tmp_path / "output")
        content = result[0].read_text()
        assert "indexableSubclass: #VarArray" in content

    def test_extension_no_class_def(self, tmp_path):
        """Extensions should not generate a class definition."""
        result = transpile_filetree_package(PACKAGE_DIR, tmp_path / "output")
        content = result[0].read_text()
        # String extension should not have a subclass: definition
        assert "subclass: #String" not in content
        assert "Extension: String" in content
