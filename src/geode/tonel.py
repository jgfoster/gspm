"""Tonel (.st) parser and Topaz (.tpz) code generator.

Parses Pharo/GemStone Tonel format files and generates equivalent Topaz
fileIn format (.tpz) that GemStone can load.
"""

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from geode.errors import TonelError


_CLASS_NAME_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TonelMethod:
    """A single method parsed from a Tonel file."""

    selector: str
    category: str
    is_class_side: bool
    source: str  # method body (lines after the selector declaration)


@dataclass
class TonelClass:
    """A class or extension parsed from a Tonel file."""

    name: str
    superclass: str = ""
    inst_vars: List[str] = field(default_factory=list)
    class_vars: List[str] = field(default_factory=list)
    class_inst_vars: List[str] = field(default_factory=list)
    pool_dictionaries: List[str] = field(default_factory=list)
    category: str = ""
    is_extension: bool = False
    comment: str = ""
    class_type: str = "normal"  # "normal" or "variable" (indexable)
    methods: List[TonelMethod] = field(default_factory=list)


# ---------------------------------------------------------------------------
# STON parser (minimal subset)
# ---------------------------------------------------------------------------


def _parse_ston(text: str) -> dict:
    """Parse a STON metadata block like { #key : value, ... }.

    Handles the subset used in Tonel:
    - Symbol values: #name, #'quoted name'
    - String values: 'string'
    - Array values: [ 'item', 'item' ] or #( item item )
    - Empty arrays: [], #()
    """
    text = text.strip()
    if not text.startswith("{") or not text.endswith("}"):
        raise TonelError(f"Expected STON block, got: {text[:50]}")

    inner = text[1:-1].strip()
    result: dict = {}

    # Tokenize by splitting on top-level commas (not inside brackets)
    pairs = _split_ston_pairs(inner)

    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue

        # Split on first ' : ' (STON key-value separator)
        match = re.match(r"(#\S+|#'[^']*')\s*:\s*(.*)", pair, re.DOTALL)
        if not match:
            continue

        key = _parse_ston_symbol(match.group(1))
        value = _parse_ston_value(match.group(2).strip())
        result[key] = value

    return result


def _split_ston_pairs(text: str) -> List[str]:
    """Split STON pairs by top-level commas, respecting brackets and quotes."""
    pairs: List[str] = []
    depth = 0
    in_quote = False
    current: List[str] = []

    for ch in text:
        if ch == "'" and depth == 0:
            in_quote = not in_quote
            current.append(ch)
        elif in_quote:
            current.append(ch)
        elif ch in ("[", "("):
            depth += 1
            current.append(ch)
        elif ch in ("]", ")"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            pairs.append("".join(current))
            current = []
        else:
            current.append(ch)

    if current:
        pairs.append("".join(current))

    return pairs


def _parse_ston_symbol(text: str) -> str:
    """Parse a STON symbol: #name or #'quoted name'."""
    text = text.strip()
    if text.startswith("#'") and text.endswith("'"):
        return text[2:-1]
    if text.startswith("#"):
        return text[1:]
    return text


def _parse_ston_value(text: str):
    """Parse a STON value (symbol, string, array, or number)."""
    text = text.strip()

    # Array: [ ... ]
    if text.startswith("["):
        return _parse_ston_array(text)

    # Array: #( ... )
    if text.startswith("#("):
        return _parse_ston_paren_array(text)

    # Symbol: #name or #'quoted'
    if text.startswith("#"):
        return _parse_ston_symbol(text)

    # String: 'quoted string'
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]

    # Number
    try:
        return int(text)
    except ValueError:
        pass

    # Boolean / nil
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "nil":
        return None

    return text


def _parse_ston_array(text: str) -> list:
    """Parse [ 'item', 'item' ] or [ #item, #item ]."""
    text = text.strip()
    if text == "[]":
        return []
    inner = text[1:-1].strip()
    if not inner:
        return []
    items = _split_ston_pairs(inner)
    return [_parse_ston_value(item.strip()) for item in items if item.strip()]


def _parse_ston_paren_array(text: str) -> list:
    """Parse #( item item ) — space-separated symbols."""
    text = text.strip()
    if text in ("#()", "#( )"):
        return []
    inner = text[2:-1].strip()
    if not inner:
        return []
    return [s.strip().lstrip("#").strip("'") for s in inner.split() if s.strip()]


# ---------------------------------------------------------------------------
# Tonel parser
# ---------------------------------------------------------------------------


def parse_tonel(content: str) -> TonelClass:
    """Parse a single Tonel .st file into a TonelClass."""
    content = content.replace("\r\n", "\n")

    # Extract optional leading comment
    comment = ""
    rest = content.lstrip()
    if rest.startswith('"'):
        end = rest.index('"', 1)
        comment = rest[1:end]
        rest = rest[end + 1:].lstrip()

    # Determine type: Class or Extension
    is_extension = False
    if rest.startswith("Extension"):
        is_extension = True
        rest = rest[len("Extension"):].lstrip()
    elif rest.startswith("Class"):
        rest = rest[len("Class"):].lstrip()
    else:
        raise TonelError(
            f"Expected 'Class' or 'Extension' declaration, got: {rest[:40]}"
        )

    # Parse the metadata block { ... }
    meta_start = rest.index("{")
    meta_end = _find_matching_brace(rest, meta_start)
    meta_text = rest[meta_start:meta_end + 1]
    meta = _parse_ston(meta_text)

    name = meta.get("name", "")
    if not name:
        raise TonelError("Missing #name in Tonel metadata")

    tonel = TonelClass(
        name=name,
        superclass=meta.get("superclass", "") if not is_extension else "",
        inst_vars=_ensure_list(meta.get("instVars", [])),
        class_vars=_ensure_list(meta.get("classVars", [])),
        class_inst_vars=_ensure_list(meta.get("classInstVars", [])),
        pool_dictionaries=_ensure_list(meta.get("poolDictionaries", [])),
        category=meta.get("category", ""),
        is_extension=is_extension,
        comment=comment,
    )

    # Parse methods after the metadata block
    methods_text = rest[meta_end + 1:]
    tonel.methods = _parse_methods(methods_text, name)

    return tonel


def _find_matching_brace(text: str, start: int) -> int:
    """Find the index of the matching closing brace."""
    depth = 0
    in_quote = False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "'" :
            in_quote = not in_quote
        elif not in_quote:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
    raise TonelError("Unmatched brace in Tonel metadata")


def _parse_methods(text: str, class_name: str) -> List[TonelMethod]:
    """Extract all methods from the text following the class metadata."""
    methods: List[TonelMethod] = []
    text = text.strip()
    if not text:
        return methods

    # Split into method blocks.
    # Each method is preceded by optional metadata { #category : ... }
    # and a declaration like: ClassName >> selector [ ... ]
    # or: ClassName class >> selector [ ... ]

    # Pattern: find method declarations
    # We split on the pattern of a metadata block or method header
    parts = _split_method_blocks(text, class_name)

    for category, is_class_side, selector, body in parts:
        methods.append(TonelMethod(
            selector=selector,
            category=category,
            is_class_side=is_class_side,
            source=body,
        ))

    return methods


def _split_method_blocks(
    text: str, class_name: str
) -> List[Tuple[str, bool, str, str]]:
    """Split text into (category, is_class_side, selector, body) tuples."""
    results: List[Tuple[str, bool, str, str]] = []
    pos = 0

    while pos < len(text):
        # Skip whitespace
        while pos < len(text) and text[pos] in " \t\n\r":
            pos += 1
        if pos >= len(text):
            break

        # Look for optional metadata block
        category = "as yet unclassified"
        if text[pos] == "{":
            meta_end = _find_matching_brace(text, pos)
            meta_text = text[pos:meta_end + 1]
            meta = _parse_ston(meta_text)
            category = meta.get("category", category)
            pos = meta_end + 1

            # Skip whitespace after metadata
            while pos < len(text) and text[pos] in " \t\n\r":
                pos += 1

        if pos >= len(text):
            break

        # Parse method declaration: ClassName [class] >> selector [
        # Find the >> separator
        arrow_pos = text.find(">>", pos)
        if arrow_pos == -1:
            break

        # Determine if class-side
        prefix = text[pos:arrow_pos].strip()
        is_class_side = prefix.endswith("class")

        # After >>, find the selector and body
        after_arrow = text[arrow_pos + 2:].lstrip()

        # The method body is enclosed in [ ... ] with balanced brackets
        bracket_pos = after_arrow.find("[")
        if bracket_pos == -1:
            break

        raw_selector = after_arrow[:bracket_pos].strip()
        selector = _extract_selector(raw_selector)

        # Find the matching ]
        abs_bracket_start = arrow_pos + 2 + (len(text[arrow_pos + 2:]) - len(after_arrow)) + bracket_pos
        bracket_end = _find_matching_bracket(text, abs_bracket_start)

        body = text[abs_bracket_start + 1:bracket_end].strip()

        # Clean up: remove leading/trailing newlines from body
        body = body.strip("\n").rstrip()

        results.append((category, is_class_side, selector, body))

        pos = bracket_end + 1

    return results


def _find_matching_bracket(text: str, start: int) -> int:
    """Find the matching ] for a [ at position start."""
    depth = 0
    in_quote = False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "'":
            in_quote = not in_quote
        elif not in_quote:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return i
    raise TonelError("Unmatched bracket in Tonel method body")


def _extract_selector(declaration: str) -> str:
    """Extract the Smalltalk selector from a method declaration.

    Examples:
        "name"           -> "name"       (unary)
        "name: aString"  -> "name:"      (keyword)
        "at: key put: val" -> "at:put:"  (multi-keyword)
        "+ other"        -> "+"           (binary)
    """
    declaration = declaration.strip()
    if not declaration:
        return ""

    # Binary selectors: start with special chars
    if declaration[0] in "+-*/~<>=@%|&!?,\\":
        # Binary: take just the operator chars
        i = 0
        while i < len(declaration) and declaration[i] not in " \t":
            i += 1
        return declaration[:i]

    # Check if it's a keyword message (contains ':')
    if ":" in declaration:
        # Extract keyword parts: each "word:" before a parameter name
        parts = declaration.split()
        keywords = [p for p in parts if p.endswith(":")]
        if keywords:
            return "".join(keywords)

    # Unary: just the first word
    return declaration.split()[0] if declaration else ""


def _ensure_list(value) -> list:
    """Ensure a value is a list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


# ---------------------------------------------------------------------------
# Topaz (.tpz) code generator
# ---------------------------------------------------------------------------


def generate_tpz(tonel: TonelClass) -> str:
    """Convert a parsed TonelClass into Topaz fileIn (.tpz) format.

    Generates class definition followed by methods — suitable for
    single-class output.  For multi-class directories, prefer
    ``generate_combined_tpz`` which separates all definitions from
    all methods to handle forward references.
    """
    def_lines = _generate_class_def(tonel)
    method_lines = _generate_methods(tonel)
    return "\n".join(def_lines + [""] + method_lines)


def generate_combined_tpz(classes: List[TonelClass]) -> str:
    """Generate a single .tpz with all class definitions first, then all methods.

    This two-phase layout ensures every class name exists in the dictionary
    before any method body is compiled, eliminating forward-reference errors.
    Classes should already be in load order (superclasses first, extensions last).
    """
    lines: List[str] = []

    # Phase 1: all class definitions
    lines.append("! Phase 1: class definitions")
    for tc in classes:
        lines.extend(_generate_class_def(tc))
        lines.append("")

    # Phase 2: all methods
    lines.append("! Phase 2: methods")
    for tc in classes:
        method_lines = _generate_methods(tc)
        if method_lines:
            lines.extend(method_lines)
            lines.append("")

    return "\n".join(lines)


def _generate_class_def(tonel: TonelClass) -> List[str]:
    """Generate the class/extension definition block (no methods)."""
    lines: List[str] = []

    if tonel.is_extension:
        lines.append(f"! Extension: {tonel.name}")
    else:
        lines.append(f"! Class: {tonel.name}")

        if tonel.comment:
            lines.append(f"!  {tonel.comment}")

        inst_vars = " ".join(tonel.inst_vars)
        class_vars = " ".join(f"#{v}" for v in tonel.class_vars)
        class_inst_vars = " ".join(tonel.class_inst_vars)
        pools = " ".join(tonel.pool_dictionaries)

        superclass = tonel.superclass or "Object"

        lines.append("doit")
        if tonel.class_type == "variable":
            lines.append(f"{superclass} indexableSubclass: #{tonel.name}")
        else:
            lines.append(f"{superclass} subclass: #{tonel.name}")
        lines.append(f"    instVarNames: #( {inst_vars})")
        lines.append(f"    classVars: #[ {class_vars}]")
        lines.append(f"    classInstVars: #( {class_inst_vars})")
        lines.append(f"    poolDictionaries: #( {pools})")
        lines.append("    inDictionary: Globals")
        lines.append("    options: #()")
        lines.append("%")

    return lines


def _generate_methods(tonel: TonelClass) -> List[str]:
    """Generate method definitions for a class (no class definition)."""
    lines: List[str] = []

    instance_methods = [m for m in tonel.methods if not m.is_class_side]
    class_methods = [m for m in tonel.methods if m.is_class_side]

    if instance_methods:
        lines.append(f"! Instance methods for {tonel.name}")
        for method in instance_methods:
            lines.append(f"category: #{method.category}")
            lines.append(f"method: {tonel.name}")
            lines.append(method.source)
            lines.append("%")
            lines.append("")

    if class_methods:
        lines.append(f"! Class methods for {tonel.name}")
        for method in class_methods:
            lines.append(f"category: #{method.category}")
            lines.append(f"classmethod: {tonel.name}")
            lines.append(method.source)
            lines.append("%")
            lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Directory processing
# ---------------------------------------------------------------------------


def discover_tonel_files(directory: Path) -> List[Path]:
    """Find all .st files in a directory."""
    if not directory.is_dir():
        raise TonelError(f"Tonel directory not found: {directory}")
    return sorted(directory.glob("*.st"))


def determine_load_order(classes: List[TonelClass]) -> List[TonelClass]:
    """Sort classes so superclasses come before subclasses, extensions last.

    Classes whose superclass is not in the list (e.g. Object) are treated
    as having no local dependency.
    """
    # Separate classes and extensions
    class_defs = [c for c in classes if not c.is_extension]
    extensions = [c for c in classes if c.is_extension]

    if not class_defs:
        return extensions

    # Build name set for local classes
    local_names = {c.name for c in class_defs}

    # Build dependency graph: class -> depends on (superclass, if local)
    in_degree: Dict[str, int] = {c.name: 0 for c in class_defs}
    dependents: Dict[str, List[str]] = defaultdict(list)

    for c in class_defs:
        if c.superclass in local_names:
            in_degree[c.name] += 1
            dependents[c.superclass].append(c.name)

    # Kahn's algorithm
    queue: deque = deque()
    for name, degree in in_degree.items():
        if degree == 0:
            queue.append(name)

    sorted_names: List[str] = []
    while queue:
        name = queue.popleft()
        sorted_names.append(name)
        for dep in dependents.get(name, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(sorted_names) != len(class_defs):
        raise TonelError("Circular inheritance detected in Tonel files")

    name_to_class = {c.name: c for c in class_defs}
    result = [name_to_class[n] for n in sorted_names]

    # Extensions come after all class definitions
    result.extend(extensions)

    return result


def parse_and_order_tonel(src_dir: Path) -> List[Tuple[Path, TonelClass]]:
    """Parse all .st files in src_dir and return (path, class) pairs in load order.

    Used by both transpilation and the TFILE-based loading path.
    """
    st_files = discover_tonel_files(src_dir)
    if not st_files:
        return []

    parsed: List[Tuple[Path, TonelClass]] = []
    for st_file in st_files:
        try:
            content = st_file.read_text()
            tonel = parse_tonel(content)
            parsed.append((st_file, tonel))
        except TonelError:
            raise
        except Exception as e:
            raise TonelError(f"Failed to parse {st_file.name}: {e}") from e

    classes = [tc for _, tc in parsed]
    ordered_classes = determine_load_order(classes)

    cls_to_path = {id(tc): p for p, tc in parsed}
    return [(cls_to_path[id(tc)], tc) for tc in ordered_classes]


def has_forward_class_refs(ordered: List[Tuple[Path, TonelClass]]) -> bool:
    """Detect whether any class's methods textually reference a peer not yet loaded.

    TFILE loads files one at a time in load order; each file's class
    definition runs before its method bodies. So a method body can
    safely reference any class defined in a previously TFILE'd file or
    in the current file. A reference to a peer class that comes later
    in the load order would fail to compile under TFILE.

    A False result means TFILE is safe; True means transpilation
    (which uses two-phase loading) is required. The check is textual
    and may produce false positives (names mentioned in comments or
    strings) — those force the safe fallback.
    """
    if len(ordered) < 2:
        return False

    local_class_names = {tc.name for _, tc in ordered if not tc.is_extension}
    if not local_class_names:
        return False

    defined: Set[str] = set()
    for _path, tc in ordered:
        if not tc.is_extension:
            defined.add(tc.name)
        for method in tc.methods:
            for ref in _CLASS_NAME_RE.findall(method.source):
                if ref in local_class_names and ref not in defined:
                    return True
    return False


def transpile_directory(src_dir: Path, dest_dir: Path) -> List[Path]:
    """Parse all .st files in src_dir, generate a single combined .tpz in dest_dir.

    The combined file uses two-phase loading: all class definitions first
    (so every class name exists before any method body is compiled), then
    all methods.  Returns a single-element list with the path to the
    generated .tpz file.
    """
    ordered = parse_and_order_tonel(src_dir)
    if not ordered:
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    tpz_path = dest_dir / f"{src_dir.name}.tpz"
    tpz_content = generate_combined_tpz([tc for _, tc in ordered])
    tpz_path.write_text(tpz_content)

    return [tpz_path]
