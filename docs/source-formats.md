# Source Formats

Geode can load GemStone code from three source formats. This guide explains
each format, when to use it, and how to configure `gemstone.toml`.

## Topaz (.gs / .tpz)

Topaz is GemStone's native file-in format. Files contain class definitions,
method definitions, and `doit` blocks that Topaz executes directly.

**When to use:** Your own project code, scripts, or any code written
specifically for GemStone.

**Example:**

```toml
[load]
files = [
    "src/core.gs",
    "src/models.gs",
    "src/app.gs",
]
```

Files are loaded in the order listed. Each file can contain class definitions,
methods, and arbitrary `doit` blocks.

**Sample project:** [samples/minimal/](../samples/minimal/) — a bare-bones
project with `.gs` source files and no dependencies.

---

## Tonel

Tonel stores one class per `.class.st` file with STON metadata headers. It
is used by Rowan, Magritte, and newer Smalltalk projects.

**Directory layout:**

```
source/
  Magritte-Model/
    MaDescription.class.st
    MaContainer.class.st
    package.st
```

Each `.class.st` file contains a STON class definition followed by all
methods for that class.

**When to use:** Depending on a library that uses Tonel format (Magritte,
Rowan packages), or writing your own code in Tonel.

### As a dependency override

```toml
[dependencies]
magritte = { version = "^3.7", git = "https://github.com/magritte-metamodel/Magritte", tonel = [
    "source/Magritte-Model",
    "source/Magritte-GemStone-Model",
]}
```

List the Tonel directories you need. Geode transpiles each directory into a
two-phase Topaz script (class definitions first, then methods) that handles
forward references automatically.

### As your project's own source

```toml
[load]
tonel = [
    "src/MyApp-Core",
    "src/MyApp-Web",
]
```

**Auto-discovery:** If no `tonel`, `filetree`, or `files` are specified for a
dependency, Geode recursively searches the cloned repository for Tonel
directories (folders containing `.class.st` files) and loads all that it
finds, excluding test directories.

**Sample project:** [samples/tonel-project/](../samples/tonel-project/) —
a project whose own source is written in Tonel format.

---

## FileTree

FileTree (also called Cypress format) stores one method per `.st` file,
organized under `.package/` directories. It is used by Seaside, Grease,
Zinc, STON, tODE, and GLASS — the most widely-deployed GemStone packages.

**Directory layout:**

```
repository/
  Seaside-Core.package/
    WAComponent.class/
      properties.json       # class metadata (name, super, instvars, ...)
      README.md             # class comment
      instance/
        initialize.st       # line 1: category, line 2+: method source
        renderContentOn..st  # dots encode colons (renderContentOn:)
      class/
        canBeRoot.st
    String.extension/
      properties.json
      instance/
        seasideUrl.st       # extension methods (category starts with *)
```

**When to use:** Depending on a library that uses FileTree format (Seaside,
Grease, Zinc, STON).

### As a dependency override

```toml
[dependencies]
seaside = { version = "^3.5", git = "https://github.com/SeasideSt/Seaside", filetree = [
    "repository/Seaside-Core.package",
    "repository/Seaside-Canvas.package",
    "repository/Seaside-Session.package",
    "repository/Seaside-Component.package",
]}
```

List the `.package` directories you need. Geode parses each package's class
definitions and methods, sorts them by inheritance order, and generates a
two-phase Topaz script — identical to Tonel output.

### Auto-discovery

If no overrides are specified, Geode also searches for `.package/` directories
alongside Tonel directories. Test packages (names containing `-Tests` or
`-Test`) are skipped automatically.

**Sample projects:**
- [samples/seaside/](../samples/seaside/) — Seaside web app with FileTree
  dependencies (Seaside, Grease) and a Tonel dependency (Magritte)
- [samples/grease/](../samples/grease/) — Grease portability layer with
  conditional loading for different GemStone versions
- [samples/zinc/](../samples/zinc/) — HTTP client using Zinc

---

## Mixing formats

A single project can use all three formats. Dependencies are independent —
each can use whichever format its upstream repository provides:

```toml
[load]
files = ["src/app.gs"]                  # your code in Topaz

[dependencies]
grease  = { version = "^1.5", git = "...", filetree = ["repository/Grease-Core.package"] }
seaside = { version = "^3.5", git = "...", filetree = ["repository/Seaside-Core.package"] }
magritte = { version = "^3.7", git = "...", tonel = ["source/Magritte-Model"] }
```

Geode resolves and loads dependencies in declaration order, transpiling each
format into Topaz before loading.

---

## Variable (indexable) classes

Both Tonel and FileTree support variable-size (indexable) classes. In
FileTree, set `"type": "variable"` in `properties.json`. In Tonel, use
`#variable` in the STON class type. Geode generates `indexableSubclass:`
instead of `subclass:` in the output Topaz script.

---

## Adding dependencies via the CLI

```bash
# FileTree dependency
Geode add seaside --version "^3.5" \
    --git "https://github.com/SeasideSt/Seaside" \
    --filetree "repository/Seaside-Core.package" \
    --filetree "repository/Seaside-Component.package"

# Tonel dependency
Geode add magritte --version "^3.7" \
    --git "https://github.com/magritte-metamodel/Magritte" \
    --tonel "source/Magritte-Model"
```
