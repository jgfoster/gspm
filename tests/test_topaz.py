"""Tests for geode.topaz module."""

import pytest

from geode.models import (
    Dependency,
    Lockfile,
    Manifest,
    PackageMetadata,
    LoadSpec,
    ResolvedPackage,
    SuiteSpec,
)
from geode.topaz import topological_sort, evaluate_conditions, generate_install_script
from geode.errors import TopazError


class TestTopologicalSort:
    """Test dependency ordering."""

    def test_empty(self):
        assert topological_sort(Lockfile()) == []

    def test_single_package(self):
        lf = Lockfile(packages=[
            ResolvedPackage(name="a", version="1.0", source="git+x", sha="aaa"),
        ])
        result = topological_sort(lf)
        assert len(result) == 1
        assert result[0].name == "a"

    def test_linear_chain(self):
        """a -> b -> c should produce [c, b, a]."""
        lf = Lockfile(packages=[
            ResolvedPackage(name="a", version="1.0", source="git+x", sha="aaa", dependencies=["b"]),
            ResolvedPackage(name="b", version="1.0", source="git+x", sha="bbb", dependencies=["c"]),
            ResolvedPackage(name="c", version="1.0", source="git+x", sha="ccc"),
        ])
        result = topological_sort(lf)
        names = [p.name for p in result]
        assert names.index("c") < names.index("b")
        assert names.index("b") < names.index("a")

    def test_diamond(self):
        """a -> (b, c), b -> d, c -> d. d must come first."""
        lf = Lockfile(packages=[
            ResolvedPackage(name="a", version="1.0", source="git+x", sha="aaa", dependencies=["b", "c"]),
            ResolvedPackage(name="b", version="1.0", source="git+x", sha="bbb", dependencies=["d"]),
            ResolvedPackage(name="c", version="1.0", source="git+x", sha="ccc", dependencies=["d"]),
            ResolvedPackage(name="d", version="1.0", source="git+x", sha="ddd"),
        ])
        result = topological_sort(lf)
        names = [p.name for p in result]
        assert names.index("d") < names.index("b")
        assert names.index("d") < names.index("c")
        assert names.index("b") < names.index("a")
        assert names.index("c") < names.index("a")

    def test_independent_packages(self):
        """Two packages with no relationship."""
        lf = Lockfile(packages=[
            ResolvedPackage(name="a", version="1.0", source="git+x", sha="aaa"),
            ResolvedPackage(name="b", version="1.0", source="git+x", sha="bbb"),
        ])
        result = topological_sort(lf)
        assert len(result) == 2


class TestEvaluateConditions:
    """Test GemStone version conditional file loading."""

    def test_matches_version(self):
        conditions = {
            ">=3.7": ["platform37.gs"],
            ">=3.6,<3.7": ["platform36.gs"],
        }
        files = evaluate_conditions(conditions, "3.7.0")
        assert files == ["platform37.gs"]

    def test_matches_range(self):
        conditions = {
            ">=3.7": ["platform37.gs"],
            ">=3.6,<3.7": ["platform36.gs"],
        }
        files = evaluate_conditions(conditions, "3.6.2")
        assert files == ["platform36.gs"]

    def test_no_match(self):
        conditions = {
            ">=3.7": ["platform37.gs"],
        }
        files = evaluate_conditions(conditions, "3.5.0")
        assert files == []

    def test_none_version(self):
        conditions = {">=3.7": ["platform37.gs"]}
        files = evaluate_conditions(conditions, None)
        assert files == []


class TestGenerateInstallScript:
    """Test Topaz script generation."""

    def test_basic_script(self, tmp_path):
        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(files=["src/MyApp.gs"]),
        )
        lockfile = Lockfile()

        script = generate_install_script(
            project_root=tmp_path,
            manifest=manifest,
            lockfile=lockfile,
            stone_name="mystone",
        )

        assert "set gemstone mystone" in script
        assert "set user DataCurator pass swordfish" in script
        assert "login" in script
        assert f"input {tmp_path / 'src/MyApp.gs'}" in script
        assert "commit" in script
        assert "logout" in script
        assert "exit" in script

    def test_script_header(self, tmp_path):
        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
        )
        script = generate_install_script(
            project_root=tmp_path,
            manifest=manifest,
            lockfile=Lockfile(),
            stone_name="mystone",
        )
        assert "Geode" in script
        assert "myapp 1.0.0" in script

    def test_custom_credentials(self, tmp_path):
        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
        )
        script = generate_install_script(
            project_root=tmp_path,
            manifest=manifest,
            lockfile=Lockfile(),
            stone_name="mystone",
            user="admin",
            password="secret",
        )
        assert "set user admin pass secret" in script

    def test_includes_test_files(self, tmp_path):
        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(files=["src/MyApp.gs"]),
            test=SuiteSpec(files=["tests/MyTests.gs"]),
        )
        script = generate_install_script(
            project_root=tmp_path,
            manifest=manifest,
            lockfile=Lockfile(),
            stone_name="mystone",
            include_tests=True,
        )
        assert f"input {tmp_path / 'tests/MyTests.gs'}" in script

    def test_dep_with_files_override(self, tmp_path):
        """Dependency without manifest but with files override."""
        # Set up a fake dependency with .gs files (no gemstone.toml)
        dep_dir = tmp_path / ".geode" / "deps" / "zinc"
        dep_dir.mkdir(parents=True)
        (dep_dir / "src").mkdir()
        (dep_dir / "src" / "ZnCore.gs").write_text("! ZnCore")

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(files=["src/MyApp.gs"]),
            dependencies={
                "zinc": Dependency(
                    name="zinc", version="^1.2",
                    git="https://example.com/zinc",
                    files=["src/ZnCore.gs"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="zinc", version="1.3.0", source="git+https://example.com/zinc", sha="abc123"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert f"input {dep_dir / 'src/ZnCore.gs'}" in script

    def test_dep_with_tonel_override(self, tmp_path):
        """Dependency without manifest but with tonel override."""
        # Set up a fake dependency with .st files (no gemstone.toml)
        dep_dir = tmp_path / ".geode" / "deps" / "seaside"
        pkg_dir = dep_dir / "src" / "Seaside-Core"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "SeasideApp.st").write_text(
            '"Test class"\n'
            'Class {\n'
            "    #name : #SeasideApp,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Seaside-Core'\n"
            "}\n"
        )
        # Ensure tonel output dir exists
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "seaside": Dependency(
                    name="seaside", version="^3.5",
                    git="https://example.com/seaside",
                    tonel=["src/Seaside-Core"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="seaside", version="3.5.0", source="git+https://example.com/seaside", sha="def456"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        # Should contain a transpiled .tpz input
        assert ".tpz" in script
        assert "Object subclass: #SeasideApp" not in script  # class def is in the .tpz file, not inline

    def test_dep_auto_discover_tonel(self, tmp_path):
        """Dependency with no manifest and no overrides — auto-discovers .st files."""
        dep_dir = tmp_path / ".geode" / "deps" / "legacy"
        pkg_dir = dep_dir / "SomePackage"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "MyClass.st").write_text(
            '"Test"\n'
            'Class {\n'
            "    #name : #MyClass,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Test'\n"
            "}\n"
        )
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "legacy": Dependency(
                    name="legacy", version="^1.0",
                    git="https://example.com/legacy",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="legacy", version="1.0.0", source="git+https://example.com/legacy", sha="ghi789"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert ".tpz" in script

    def test_dep_auto_discover_gs_fallback(self, tmp_path):
        """Auto-discovery falls back to .gs files when no .st files found."""
        dep_dir = tmp_path / ".geode" / "deps" / "oldpkg"
        (dep_dir / "src").mkdir(parents=True)
        (dep_dir / "src" / "OldCode.gs").write_text("! old code")

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "oldpkg": Dependency(
                    name="oldpkg", version="^1.0",
                    git="https://example.com/oldpkg",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="oldpkg", version="1.0.0", source="git+https://example.com/oldpkg", sha="jkl012"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert f"input {dep_dir / 'src' / 'OldCode.gs'}" in script

    def test_dep_auto_discover_nested_tonel(self, tmp_path):
        """Auto-discovery finds .st files in nested directories (e.g., src/PkgName/)."""
        dep_dir = tmp_path / ".geode" / "deps" / "rowan_style"
        pkg_dir = dep_dir / "src" / "RowanPkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "RowanClass.st").write_text(
            '"Test"\n'
            'Class {\n'
            "    #name : #RowanClass,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Test'\n"
            "}\n"
        )
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "rowan_style": Dependency(
                    name="rowan_style", version="^1.0",
                    git="https://example.com/rowan_style",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="rowan_style", version="1.0.0",
                            source="git+https://example.com/rowan_style", sha="nest01"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert ".tpz" in script

    def test_dep_auto_discover_skips_test_dirs(self, tmp_path):
        """Auto-discovery skips test directories."""
        dep_dir = tmp_path / ".geode" / "deps" / "withtest"
        # Production package
        prod_dir = dep_dir / "Seaside-Core"
        prod_dir.mkdir(parents=True)
        (prod_dir / "SeasideApp.st").write_text(
            '"Test"\n'
            'Class {\n'
            "    #name : #SeasideApp,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Seaside-Core'\n"
            "}\n"
        )
        # Test package (should be skipped)
        test_dir = dep_dir / "Seaside-Tests"
        test_dir.mkdir(parents=True)
        (test_dir / "SeasideTest.st").write_text(
            '"Test"\n'
            'Class {\n'
            "    #name : #SeasideTest,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Seaside-Tests'\n"
            "}\n"
        )
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "withtest": Dependency(
                    name="withtest", version="^1.0",
                    git="https://example.com/withtest",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="withtest", version="1.0.0",
                            source="git+https://example.com/withtest", sha="skip01"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert "Seaside-Core" in script
        assert "Seaside-Tests" not in script

    def test_dep_auto_discover_gs_recursive(self, tmp_path):
        """Auto-discovery finds .gs files recursively, not just in src/."""
        dep_dir = tmp_path / ".geode" / "deps" / "deepgs"
        (dep_dir / "lib" / "core").mkdir(parents=True)
        (dep_dir / "lib" / "core" / "Deep.gs").write_text("! deep code")

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "deepgs": Dependency(
                    name="deepgs", version="^1.0",
                    git="https://example.com/deepgs",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="deepgs", version="1.0.0",
                            source="git+https://example.com/deepgs", sha="deep01"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert f"input {dep_dir / 'lib' / 'core' / 'Deep.gs'}" in script

    def test_dep_auto_discover_gs_skips_test_dirs(self, tmp_path):
        """Auto-discovery of .gs files skips test directories."""
        dep_dir = tmp_path / ".geode" / "deps" / "gstest"
        (dep_dir / "src").mkdir(parents=True)
        (dep_dir / "src" / "Prod.gs").write_text("! production")
        (dep_dir / "tests").mkdir(parents=True)
        (dep_dir / "tests" / "TestCode.gs").write_text("! test")

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "gstest": Dependency(
                    name="gstest", version="^1.0",
                    git="https://example.com/gstest",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="gstest", version="1.0.0",
                            source="git+https://example.com/gstest", sha="gst01"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert f"input {dep_dir / 'src' / 'Prod.gs'}" in script
        assert "TestCode.gs" not in script

    def test_dep_with_filetree_override(self, tmp_path):
        """Dependency without manifest but with filetree override."""
        dep_dir = tmp_path / ".geode" / "deps" / "grease"
        pkg_dir = dep_dir / "repository" / "Grease-Core.package"
        cls_dir = pkg_dir / "GRObject.class"
        cls_dir.mkdir(parents=True)
        (cls_dir / "properties.json").write_text(
            '{"name":"GRObject","super":"Object","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"Grease-Core","type":"normal"}'
        )
        inst_dir = cls_dir / "instance"
        inst_dir.mkdir()
        (inst_dir / "greaseString.st").write_text("printing\ngreaseString\n\t^ self printString")
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(files=["src/MyApp.gs"]),
            dependencies={
                "grease": Dependency(
                    name="grease", version="^1.0",
                    git="https://example.com/grease",
                    filetree=["repository/Grease-Core.package"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="grease", version="1.0.0",
                            source="git+https://example.com/grease", sha="ft001"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert ".tpz" in script
        assert "Grease-Core" in script

    def test_dep_auto_discover_filetree(self, tmp_path):
        """Auto-discovery finds .package/ directories."""
        dep_dir = tmp_path / ".geode" / "deps" / "oldlib"
        pkg_dir = dep_dir / "repository" / "OldLib-Core.package"
        cls_dir = pkg_dir / "OldClass.class"
        cls_dir.mkdir(parents=True)
        (cls_dir / "properties.json").write_text(
            '{"name":"OldClass","super":"Object","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"OldLib-Core","type":"normal"}'
        )
        inst_dir = cls_dir / "instance"
        inst_dir.mkdir()
        (inst_dir / "run.st").write_text("actions\nrun\n\t^ 42")
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "oldlib": Dependency(
                    name="oldlib", version="^1.0",
                    git="https://example.com/oldlib",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="oldlib", version="1.0.0",
                            source="git+https://example.com/oldlib", sha="ft002"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert ".tpz" in script

    def test_use_tfile_emits_tfile_directives(self, tmp_path):
        """With use_tfile=True and no forward refs, emit TFILE per .st file."""
        dep_dir = tmp_path / ".geode" / "deps" / "tfilepkg"
        pkg_dir = dep_dir / "src" / "Pkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "OneClass.st").write_text(
            'Class {\n'
            "    #name : #OneClass,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Pkg'\n"
            "}\n"
        )

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "tfilepkg": Dependency(
                    name="tfilepkg", version="^1.0",
                    git="https://example.com/tfilepkg",
                    tonel=["src/Pkg"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="tfilepkg", version="1.0.0",
                            source="git+https://example.com/tfilepkg", sha="tf001"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
            use_tfile=True,
        )
        assert f"TFILE {pkg_dir / 'OneClass.st'}" in script
        # Should NOT have transpiled
        assert ".tpz" not in script

    def test_use_tfile_falls_back_when_forward_refs(self, tmp_path):
        """With use_tfile=True but forward refs present, transpile instead."""
        dep_dir = tmp_path / ".geode" / "deps" / "cyclic"
        pkg_dir = dep_dir / "src" / "Cycle"
        pkg_dir.mkdir(parents=True)
        # Alpha references Beta; Alpha loads first (alphabetical) → forward ref
        (pkg_dir / "Alpha.st").write_text(
            'Class {\n'
            "    #name : #Alpha,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Cycle'\n"
            "}\n"
            "\n"
            "{ #category : #x }\n"
            "Alpha >> useBeta [\n"
            "    ^ Beta new\n"
            "]\n"
        )
        (pkg_dir / "Beta.st").write_text(
            'Class {\n'
            "    #name : #Beta,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Cycle'\n"
            "}\n"
        )
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "cyclic": Dependency(
                    name="cyclic", version="^1.0",
                    git="https://example.com/cyclic",
                    tonel=["src/Cycle"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="cyclic", version="1.0.0",
                            source="git+https://example.com/cyclic", sha="cy001"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
            use_tfile=True,
        )
        # Should have fallen back to .tpz, with a comment explaining why
        assert ".tpz" in script
        assert "TFILE skipped for Cycle" in script
        assert "TFILE " not in script.replace("TFILE skipped", "")

    def test_use_tfile_default_is_transpile(self, tmp_path):
        """Without --tfile (default), behavior is unchanged: transpile."""
        dep_dir = tmp_path / ".geode" / "deps" / "regular"
        pkg_dir = dep_dir / "src" / "Pkg"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "OneClass.st").write_text(
            'Class {\n'
            "    #name : #OneClass,\n"
            "    #superclass : #Object,\n"
            "    #instVars : [],\n"
            "    #classVars : [],\n"
            "    #poolDictionaries : [],\n"
            "    #category : #'Pkg'\n"
            "}\n"
        )

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "regular": Dependency(
                    name="regular", version="^1.0",
                    git="https://example.com/regular",
                    tonel=["src/Pkg"],
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="regular", version="1.0.0",
                            source="git+https://example.com/regular", sha="rg001"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
            # use_tfile defaults to False
        )
        assert ".tpz" in script
        assert "TFILE" not in script

    def test_dep_auto_discover_skips_filetree_test_packages(self, tmp_path):
        """Auto-discovery skips .package dirs with test names."""
        dep_dir = tmp_path / ".geode" / "deps" / "withft"
        # Production package
        prod_pkg = dep_dir / "repository" / "Core.package"
        cls_dir = prod_pkg / "CoreClass.class"
        cls_dir.mkdir(parents=True)
        (cls_dir / "properties.json").write_text(
            '{"name":"CoreClass","super":"Object","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"Core","type":"normal"}'
        )
        inst_dir = cls_dir / "instance"
        inst_dir.mkdir()
        (inst_dir / "run.st").write_text("actions\nrun\n\t^ true")
        # Test package (should be skipped)
        test_pkg = dep_dir / "repository" / "Core-Tests.package"
        tcls_dir = test_pkg / "CoreTest.class"
        tcls_dir.mkdir(parents=True)
        (tcls_dir / "properties.json").write_text(
            '{"name":"CoreTest","super":"TestCase","instvars":[],'
            '"classvars":[],"classinstvars":[],"pools":[],'
            '"category":"Core-Tests","type":"normal"}'
        )
        tinst_dir = tcls_dir / "instance"
        tinst_dir.mkdir()
        (tinst_dir / "testRun.st").write_text("tests\ntestRun\n\tself assert: true")
        (tmp_path / ".geode" / "tonel").mkdir(parents=True, exist_ok=True)

        manifest = Manifest(
            package=PackageMetadata(name="myapp", version="1.0.0"),
            load=LoadSpec(),
            dependencies={
                "withft": Dependency(
                    name="withft", version="^1.0",
                    git="https://example.com/withft",
                ),
            },
        )
        lockfile = Lockfile(packages=[
            ResolvedPackage(name="withft", version="1.0.0",
                            source="git+https://example.com/withft", sha="ft003"),
        ])

        script = generate_install_script(
            project_root=tmp_path, manifest=manifest,
            lockfile=lockfile, stone_name="mystone",
        )
        assert "Core.tpz" in script
        assert "Core-Tests" not in script
