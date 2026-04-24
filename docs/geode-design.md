# GemStone Package Manager (geode) — Design Document

A Cargo-inspired package manager for GemStone using `.gs` / `.tpz` file-in format
(with Tonel `.st` transpilation), managed on disk with Git and loaded via a Python
CLI that generates Topaz scripts.

> This document records the design rationale and architecture of Geode. For
> usage instructions, see the [README](../README.md).

---

## Why Files, Not Images

The Smalltalk tradition treats the live image as the source of truth, with
files as a secondary export. Geode inverts this: files are canonical, and the
image is a build artifact derived from them. Three commonly cited objections
to this inversion do not survive scrutiny.

**"Smalltalk is a live object graph, not files."** True, and so is Python's
runtime once you `import` a module — a live namespace subject to monkey-patching
and reflection. The practical flow is the same in both: start with a base
runtime, load packages, run. Starting from a vendor image instead of an
interpreter binary is a distribution detail, not a semantic one.

**"Loading into GemStone is a database migration."** Only when a class's shape
changes *and* persistent instances of that class exist. For the common case —
loading a new package, or reloading one whose class layout is unchanged — the
class builder is a no-op, exactly as `ALTER TABLE` is a no-op when the schema
is already current. Schema evolution is a real operational concern, but it is
orthogonal to package management.

**"There is no separate build step."** A framing choice, not a technical one.
Metacello collapses fetch and load into a single image-side operation. The
Topaz CLI makes it straightforward to split them, and Geode does: `geode fetch`
resolves and downloads to disk; `geode install` generates and runs a Topaz
script. Either step can be inspected before the next one runs.

The one genuine distinction is workflow *direction*: most Smalltalkers edit
code inside the image and export to files, rather than editing files and
loading into the image. Geode does not solve the export direction — it assumes
files are where you edit. For projects willing to accept that constraint,
every other part of the pipeline is standard.

---

## The Manifest File: `gemstone.toml`

TOML is a natural choice for the manifest because it is simple, human-readable,
Git-friendly (diffs well), and parseable from bash using `tomlq` or `dasel`, or
trivially with Python — which is available on every system you would run GemStone on.
No Smalltalk is needed to read it.

```toml
[package]
name = "seaside"
version = "3.5.0"
description = "Web application framework for GemStone"
gemstone = ">=3.5"          # minimum GemStone version required
authors = ["Seaside Team"]
license = "MIT"
repository = "https://github.com/SeasideSt/Seaside"

[load]
# Files to file-in, in order, relative to package root
files = [
    "src/core/SeasideCore.gs",
    "src/core/SeasideSession.gs",
    "src/rendering/SeasideRendering.gs",
    "src/adaptors/SeasideGemStone.gs"
]
# Directories containing Tonel (.st) files
tonel = ["src/MyPackage"]

[load.conditions]
# Conditional loading based on GemStone version
">=3.7"       = ["src/platform/Seaside37Features.gs"]
">=3.6,<3.7"  = ["src/platform/Seaside36Features.gs"]

[dependencies]
magritte = { version = "^2.0", git = "https://github.com/magritte-metamodel/magritte" }
zinc     = { version = "^1.2", git = "https://github.com/svenvc/zinc" }

[dev-dependencies]
# Only loaded when running tests
sunit = { version = "^1.0", git = "https://github.com/example/sunit-gs" }

[test]
files = ["tests/SeasideTests.gs"]
```

### Design notes

- The `[load]` section lists which `.gs` files to file-in and in what order. Order
  matters in Smalltalk because classes must be defined before they are referenced.
- `[load].tonel` lists directories containing Tonel `.st` files. Geode auto-discovers
  files in these directories and determines load order from the class hierarchy.
- `[load.conditions]` handles GemStone version conditional loading. The key is a
  semver range; the value is a list of additional files to load.
- Dependencies can include optional `files` and `tonel` load overrides for consuming
  packages that lack their own `gemstone.toml` (see below).
- `[dev-dependencies]` mirrors Cargo's concept — test code and test framework are
  declared separately and only loaded when explicitly requested.

### Conditional dependencies

In addition to conditional *files* (via `[load.conditions]`), the manifest
supports conditional *dependencies* — a dependency that is only activated
on certain GemStone versions or platforms:

```toml
[dependencies.gemstone.">=3.7"]
gemstone-extras = { version = "^1.0", git = "..." }

[dependencies.platform.linux]
linux-support = { version = "^1.0", git = "..." }
```

The resolver evaluates these blocks against the target environment.
`geode fetch` and `geode update` accept `--gs-version` to activate
gemstone-conditional blocks; the platform is auto-detected from the host.
A block whose dimension is not provided is skipped — so a fetch without
`--gs-version` will not include any gemstone-conditional dependencies.

`gemstone` and `platform` are reserved sub-table names under
`[dependencies]` and `[dev-dependencies]` and cannot be used as regular
dependency names. Existing manifests without conditional blocks remain
valid.

---

## The Lock File: `gemstone.lock`

```toml
# This file is automatically generated by Geode.
# Do not edit it manually. Commit it to version control.

[[package]]
name = "seaside"
version = "3.5.0"
source = "git+https://github.com/SeasideSt/Seaside"
sha = "a3f8c92d14e7b6..."

[[package]]
name = "magritte"
version = "2.1.3"
source = "git+https://github.com/magritte-metamodel/magritte"
sha = "f92b3a71cc04d8..."
dependencies = ["zinc"]

[[package]]
name = "zinc"
version = "1.3.1"
source = "git+https://github.com/svenvc/zinc"
sha = "b84c1f209d3e5a..."
```

The lockfile records the exact SHA for every resolved dependency, including transitive
ones. This is the reproducibility guarantee — committing this file means anyone who
checks out your repository gets exactly the same code.

Version numbers are the declared versions from each package's own `gemstone.toml`,
but the SHA is what actually controls what you get. The lockfile is generated by
`geode` and should never be edited by hand.

---

## Directory Structure

```
my-project/
  gemstone.toml           # manifest — you write this
  gemstone.lock           # lockfile — Geode generates this
  src/
    MyApp.gs              # your code (.gs format)
    MyModel.gs
    MyPackage/            # Tonel directory
      Customer.st
      Order.st
  tests/
    MyTests.gs
  .geode/                  # managed by Geode, gitignored
    cache/                # immutable cache of fetched SHAs
      a3f8c92d.../        # seaside at this exact SHA
      f92b3a71.../        # magritte at this exact SHA
    deps/                 # working copies for current build
      seaside/
      magritte/
      zinc/
    tonel/                # transpiled .tpz files from Tonel sources
      MyPackage/
```

The `.geode/cache/` directory stores fetched git trees keyed by SHA. Once a SHA is
in the cache it never changes — this mirrors how Cargo's registry cache works. The
`deps/` directory is populated from the cache for the current build. Both are
gitignored.

---

## The CLI Tool: `geode`

A Python CLI (using Click) with subcommands modeled on Cargo, installable via
`pip install gemstone-geode`:

```
Geode init [name]       Create a new project with a skeleton gemstone.toml
Geode add <package>     Add a dependency (updates gemstone.toml)
Geode fetch             Resolve and download all dependencies (updates gemstone.lock)
Geode install <stone>   Generate and run topaz script to load into a stone
Geode test <stone>      Load including dev-dependencies and run tests
Geode update [package]  Update dependencies within declared constraints
Geode tree              Show resolved dependency tree
Geode publish           Publish this package to a registry
```

---

## What `geode fetch` Does

This is the core resolution step, analogous to `cargo fetch` or `bundle install`:

1. Reads `gemstone.toml` and collects all declared dependencies.
2. For each dependency, fetches its `gemstone.toml` to discover its own dependencies
   (transitive resolution).
3. Runs the version resolver to find a consistent set of versions satisfying all
   constraints.
4. Records exact SHAs in `gemstone.lock`.
5. Downloads and caches each git tree at the resolved SHA.

The version resolver uses a recursive algorithm with backtracking, powered by
Python's `packaging` library for version comparison. Cargo-style caret (`^1.2`)
and tilde (`~1.2`) constraints are translated to PEP 440 specifier sets. For
each dependency, the resolver tries the highest compatible version first; if
transitive dependencies cause a conflict, it backtracks and tries the next
version down.

---

## What `geode install` Does

`geode install <stone>` generates and runs a Topaz script. Example:

```bash
Geode install my_stone
```

Generated Topaz script:

```smalltalk
! Bootstrap load script generated by Geode 0.1.0
! Project: my-project 1.0.0
! Generated: 2026-02-27T10:30:00Z

set gemstone my_stone
set user DataCurator pass swordfish
login

! Dependency: zinc 1.3.1 (b84c1f209d3e5a...)
input /home/dev/.geode/deps/zinc/src/ZnCore.gs
input /home/dev/.geode/deps/zinc/src/ZnClient.gs

! Dependency: magritte 2.1.3 (f92b3a71cc04d8...)
input /home/dev/.geode/deps/magritte/src/MADescription.gs
input /home/dev/.geode/deps/magritte/src/MAContainer.gs

! Dependency: seaside 3.5.0 (a3f8c92d14e7b6...)
input /home/dev/.geode/deps/seaside/src/core/SeasideCore.gs
input /home/dev/.geode/deps/seaside/src/core/SeasideSession.gs
! GemStone 3.7 conditional
input /home/dev/.geode/deps/seaside/src/platform/Seaside37Features.gs

! Project: my-project
input /home/dev/my-project/src/MyModel.gs
input /home/dev/my-project/src/MyApp.gs

commit
logout
exit
```

Then executes:

```bash
topaz -l -s generated_load.topaz
```

The generated script is ephemeral — created in a temp directory and discarded after
use. The only files that are stable and committed to git are `gemstone.toml` and
`gemstone.lock`.

---

## The Registry Question

Cargo works best with a central registry (crates.io). For a small GemStone community
there are two practical options:

**Git-only (no registry):** Every dependency is specified as a git URL. Simple to
start, no infrastructure required. The `gemstone.toml` files serve as a distributed
registry — you find packages by knowing their GitHub URLs.

**A lightweight registry (implemented):** A single git repository (hosted on GitHub)
containing an `index.json` file that maps package names to their git URLs and
published versions, similar to how Homebrew works. Publishing a package means
opening a pull request to the index via `geode publish` (which uses the `gh` CLI).
This gives you `geode add seaside` without needing to know the URL, and provides a
community-curated list of available packages. It requires no server infrastructure
beyond a GitHub repository, and the community is small enough that curation is
feasible.

### Why git, not OCI

An alternative design would distribute packages as OCI artifacts via `oras` to
a registry such as GitHub Container Registry. OCI gives you content-addressed
storage and standard tooling, and is a reasonable choice in the abstract.

Geode uses git instead because, for this community, git is already the
lower-friction option:

- Every GemStone package already lives in a git repository. An OCI layer would
  require authors to publish the same content twice.
- Git SHAs are content-addressed. The lockfile pins a SHA, which is the same
  reproducibility guarantee an OCI digest would provide.
- GitHub auth is already in every contributor's environment; `oras login`
  against a separate registry is one more setup step.
- The JSON index repo is a thinner publishing surface than an OCI artifact
  spec — a pull request editing one JSON file, reviewable in the usual way.

OCI transport could be added later as an alternative source type in
`gemstone.toml` without disturbing the rest of the design.

---

## Tonel Transpilation

Many GemStone and Pharo packages store code in Tonel format — one `.st` file per
class, with method definitions inline. GemStone's Topaz cannot load `.st` files
directly, so Geode includes a transpiler that converts Tonel files to `.tpz` file-in
format at install time.

This is a deliberate design choice: rather than requiring packages to ship in `.gs`
format, Geode meets the ecosystem where it is. Packages written in Tonel can be
consumed without modification. The transpiled `.tpz` files are ephemeral — stored
in `.geode/tonel/` and regenerated on each install.

### How it works

1. The manifest declares Tonel directories via `[load].tonel`.
2. During `geode install` / `geode test`, the transpiler parses each `.st` file,
   extracting the class definition (or extension) and all methods.
3. All classes from a directory are combined into a single `.tpz` file using
   **two-phase loading**:
   - **Phase 1** emits all class definitions (superclasses before subclasses) so
     that every class name exists in the symbol dictionary.
   - **Phase 2** emits all methods (instance, class, and extension). Because every
     class name is already defined, forward references in method bodies compile
     without error.
4. The generated `.tpz` file is included in the Topaz script via an `input`
   directive, just like `.gs` files.

The two-phase layout handles forward references transparently — a method in class A
can reference class B without worrying about load order. GemStone treats a duplicate
class definition as a no-op, so there is no conflict if a class also appears in a
`.gs` file.

This applies to both the project's own source and fetched dependencies — if a
dependency's `gemstone.toml` declares `tonel` directories, Geode transpiles them
automatically.

### Native TFILE loading (opt-in)

Newer versions of Topaz support `TFILE`, which loads Tonel `.class.st` /
`.method.st` files directly without an intermediate transpile step. When
`geode install` or `geode test` is invoked with `--tfile`, the loader emits
`TFILE` directives in inheritance order instead of producing a combined
`.tpz`.

This skips the transpilation pass at the cost of two-phase forward-reference
handling: TFILE compiles each file's methods immediately, so a method body
in class A cannot reference a peer class B that comes later in the load
order. Before emitting TFILE directives, Geode scans method bodies for
references to local class names that have not yet been loaded; if any are
found, it falls back to the transpile path for that directory and notes
the fallback in the generated script. The textual scan is conservative —
false positives only force the safe fallback.

---

## Backwards Compatibility with Existing Packages

Geode is the new kid on the block — existing GemStone packages don't have a
`gemstone.toml` and shouldn't need one for Geode to consume them. Dependencies
do not require a manifest. When loading a dependency, Geode uses this priority:

1. **Has `gemstone.toml`** — use its `[load]` section (files, tonel, conditions).
2. **No manifest, but consumer declared load overrides** — the consuming project
   specifies `files` and/or `tonel` on the dependency in its own manifest:

   ```toml
   [dependencies]
   seaside = { version = "^3.5", git = "...", tonel = ["src/Seaside-Core"] }
   zinc    = { version = "^1.2", git = "...", files = ["src/ZnCore.gs"] }
   ```

3. **Neither manifest nor overrides** — Geode auto-discovers Tonel directories
   (directories containing `.st` files) and falls back to `src/*.gs`.

This makes Geode interoperable with the existing ecosystem. The person adding a
dependency knows what needs loading and can make it explicit in their own manifest.
The dependency itself never needs to change.

For version resolution, missing manifests are treated as having no transitive
dependencies — which is correct for most existing packages that were designed
for monolithic loading.

### Migration from `.mcz` and Metacello baselines

A substantial amount of existing GemStone code is distributed as Monticello
`.mcz` archives or described by Metacello baseline classes. Both are in
scope as one-way migration shims — tools that produce a geode-compatible
package from the legacy source, rather than runtime adapters.

- **`.mcz` conversion (implemented)**: `geode migrate-mcz <path>` extracts
  the archive, locates `snapshot/source.st`, strips Monticello-specific
  metadata (`stamp:`, `commentStamp:`, `prior:`) that Topaz does not
  recognize, and writes the source as a `.gs` file alongside a generated
  `gemstone.toml`. Topaz `input` reads chunk-format files directly, so no
  chunk-level parsing is required for the round-trip. Best-effort —
  packages with traits or unusual extensions may need manual review.
- **Metacello baseline parsing (roadmap)**: most baselines are formulaic —
  `package:`, `requires:`, `for: #common`, `for: #gemstone` with version
  guards. A pattern-matching parser could extract these into a generated
  `gemstone.toml`. Baselines with complex conditional Smalltalk logic
  would produce a warning and require manual review.

These are onboarding aids, not steady-state components. Once a package has
been migrated it lives in Geode the same way any other package does.

---

## What This Deliberately Omits

Compared to Rowan, this design consciously leaves out:

- Symbol dictionary assignment (handled directly in `.gs` files)
- Session methods
- Pharo/Squeak cross-platform concerns
- IDE integration
- Image-to-disk write-back

The last point is the most significant departure from the Rowan/Iceberg experience.
This design takes the position that **the `.gs` files on disk are the source of
truth**, and the GemStone image is a build artifact. You never extract code from the
image back to disk — you always edit the files and reload. This is how every other
modern programming environment works, and it provides a clean mental model — but it
is a meaningful shift from the traditional Smalltalk philosophy where the image is
the source of truth.

---

## The Key Insight

The simplicity here comes from accepting one constraint: if the files are the truth
and the image is derived from them, then none of the complexity that Rowan, Iceberg,
and Tonel exist to manage is needed. The round-trip problem (image ↔ files)
disappears entirely. The result is a tool that works with standard Git workflows
and that any programmer familiar with modern package managers would immediately
understand.

---

## Implementation

Geode is implemented as a pure Python package with three runtime dependencies:

- **Click** — CLI framework
- **tomlkit** — TOML parsing with round-trip comment/formatting preservation
- **packaging** — PEP 440 version specifiers (used by pip itself)

Git operations are handled via `subprocess` calls, avoiding any Python git
library dependency. The tool is pip-installable and requires Python 3.9+.

### Module structure

```
src/geode/
  cli.py          Click command group — wires all subcommands together
  manifest.py     Parse/write gemstone.toml, constraint translation
  lockfile.py     Parse/write gemstone.lock
  resolver.py     Dependency resolution with backtracking
  topaz.py        Topaz script generation, topological sort
  tonel.py        Tonel (.st) parser and .tpz transpiler
  registry.py     Lightweight GitHub index interaction
  git.py          Git subprocess wrapper
  cache.py        .geode/ directory management
  config.py       User configuration (~/.geode/config.toml)
  models.py       Core dataclasses
  errors.py       Exception hierarchy
```
