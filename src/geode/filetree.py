"""FileTree (.package) parser and Topaz (.tpz) code generator.

Parses Monticello/Cypress FileTree format packages and generates equivalent
Topaz fileIn format (.tpz) that GemStone can load.

FileTree stores one method per .st file, organized under .package/ directories
containing .class/ and .extension/ subdirectories.  Class metadata lives in
properties.json files.

The parser produces TonelClass/TonelMethod objects (shared with the Tonel
parser), so the existing load-ordering and two-phase TPZ generation code is
reused without modification.
"""

import json
from pathlib import Path
from typing import List

from geode.errors import FileTreeError
from geode.tonel import (
    TonelClass,
    TonelMethod,
    _extract_selector,
    determine_load_order,
    generate_combined_tpz,
)


# ---------------------------------------------------------------------------
# Method parser
# ---------------------------------------------------------------------------


def parse_filetree_method(method_path: Path, is_class_side: bool) -> TonelMethod:
    """Parse a single FileTree method .st file.

    Format: line 1 is the category, line 2+ is the method source
    (selector declaration followed by body).
    """
    content = method_path.read_text()
    lines = content.split("\n", 1)

    if len(lines) < 2 or not lines[1].strip():
        raise FileTreeError(f"Method file too short: {method_path}")

    category = lines[0].strip()
    source = lines[1].rstrip()

    # Extract selector from the first line of the method source
    first_source_line = source.split("\n", 1)[0].strip()
    selector = _extract_selector(first_source_line)

    return TonelMethod(
        selector=selector,
        category=category,
        is_class_side=is_class_side,
        source=source,
    )


# ---------------------------------------------------------------------------
# Class / extension parsers
# ---------------------------------------------------------------------------


def parse_filetree_class(class_dir: Path) -> TonelClass:
    """Parse a .class/ directory into a TonelClass.

    Reads properties.json for class metadata, README.md for the class
    comment, and scans instance/ and class/ subdirectories for methods.
    """
    props = _read_properties(class_dir)

    name = props.get("name", "")
    if not name:
        raise FileTreeError(f"Missing 'name' in {class_dir / 'properties.json'}")

    # Read class comment
    comment = ""
    readme = class_dir / "README.md"
    if readme.exists():
        comment = readme.read_text().strip()

    # Parse methods
    methods = _scan_methods(class_dir)

    return TonelClass(
        name=name,
        superclass=props.get("super", "Object"),
        inst_vars=props.get("instvars", []),
        class_vars=props.get("classvars", []),
        class_inst_vars=props.get("classinstvars", []),
        pool_dictionaries=props.get("pools", []),
        category=props.get("category", ""),
        is_extension=False,
        comment=comment,
        class_type=props.get("type", "normal"),
        methods=methods,
    )


def parse_filetree_extension(ext_dir: Path) -> TonelClass:
    """Parse a .extension/ directory into a TonelClass with is_extension=True.

    Extensions add methods to classes defined elsewhere — they have no
    superclass, instance variables, or class definition.
    """
    props = _read_properties(ext_dir)

    name = props.get("name", "")
    if not name:
        raise FileTreeError(f"Missing 'name' in {ext_dir / 'properties.json'}")

    methods = _scan_methods(ext_dir)

    return TonelClass(
        name=name,
        is_extension=True,
        methods=methods,
    )


# ---------------------------------------------------------------------------
# Package parser
# ---------------------------------------------------------------------------


def parse_filetree_package(package_dir: Path) -> List[TonelClass]:
    """Parse a .package/ directory, returning all classes and extensions."""
    if not package_dir.is_dir():
        raise FileTreeError(f"FileTree package not found: {package_dir}")

    classes: List[TonelClass] = []

    for child in sorted(package_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.endswith(".class"):
            classes.append(parse_filetree_class(child))
        elif child.name.endswith(".extension"):
            classes.append(parse_filetree_extension(child))

    return classes


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_filetree_packages(root: Path) -> List[Path]:
    """Recursively find .package/ directories under root."""
    if not root.is_dir():
        return []
    packages: List[Path] = []
    _find_filetree_packages(root, packages)
    return packages


def _find_filetree_packages(root: Path, result: List[Path]) -> None:
    """Recursively find directories ending with .package."""
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if child.name.endswith(".package"):
            result.append(child)
        else:
            _find_filetree_packages(child, result)


# ---------------------------------------------------------------------------
# Transpile entry point
# ---------------------------------------------------------------------------


def transpile_filetree_package(package_dir: Path, dest_dir: Path) -> List[Path]:
    """Parse a .package/ directory and generate a combined .tpz file.

    Returns a list containing the single output .tpz path, or an empty
    list if the package contains no classes.
    """
    classes = parse_filetree_package(package_dir)
    if not classes:
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)

    ordered = determine_load_order(classes)

    # Name the .tpz after the package (strip .package suffix)
    pkg_name = package_dir.name
    if pkg_name.endswith(".package"):
        pkg_name = pkg_name[: -len(".package")]

    tpz_path = dest_dir / f"{pkg_name}.tpz"
    tpz_content = generate_combined_tpz(ordered)
    tpz_path.write_text(tpz_content)

    return [tpz_path]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_properties(directory: Path) -> dict:
    """Read and parse properties.json from a .class/ or .extension/ dir."""
    props_path = directory / "properties.json"
    if not props_path.exists():
        raise FileTreeError(f"Missing properties.json in {directory}")

    try:
        return json.loads(props_path.read_text())
    except json.JSONDecodeError as e:
        raise FileTreeError(f"Invalid JSON in {props_path}: {e}") from e


def _scan_methods(directory: Path) -> List[TonelMethod]:
    """Scan instance/ and class/ subdirectories for method .st files."""
    methods: List[TonelMethod] = []

    instance_dir = directory / "instance"
    if instance_dir.is_dir():
        for st_file in sorted(instance_dir.glob("*.st")):
            methods.append(parse_filetree_method(st_file, is_class_side=False))

    class_dir = directory / "class"
    if class_dir.is_dir():
        for st_file in sorted(class_dir.glob("*.st")):
            methods.append(parse_filetree_method(st_file, is_class_side=True))

    return methods
