# Changelog

## 0.2.0 — 2026-04-24

### Renamed

- Project renamed from `gspm` to `geode`. PyPI distribution is now
  `gemstone-geode`; the CLI command is `geode`. Hidden working directory
  in projects is now `.geode/` (was `.gspm/`); global config is now
  `~/.geode/config.toml` (was `~/.gspm/config.toml`); the default registry
  index repo is `GemTalk/geode-index` (was `GemTalk/gspm-index`).
- This is a clean rename with no compatibility shim. Existing `.gspm/`
  directories are not recognized — re-run `geode fetch` to re-populate
  under `.geode/`.

### Added

- **TFILE-based Tonel loading** (opt-in): `geode install --tfile` and
  `geode test --tfile` emit `TFILE` directives directly against
  `.class.st` files in inheritance order instead of transpiling to a
  combined `.tpz`. A textual scan detects peer-class forward references
  in method bodies and falls back to transpilation for affected
  directories.
- **Conditional dependencies**: `[dependencies.gemstone.">=X"]` and
  `[dependencies.platform.<name>]` blocks (also under
  `[dev-dependencies]`) declare deps that activate only when the target
  environment matches. The resolver evaluates the blocks; `geode fetch`
  and `geode update` accept `--gs-version` and auto-detect the platform.
- **`geode migrate-mcz`**: best-effort one-way migration of Monticello
  `.mcz` archives. Extracts `snapshot/source.st`, strips Monticello
  metadata (`stamp:`, `commentStamp:`, `prior:`), and writes a `.gs`
  file plus a generated `gemstone.toml`. Topaz `input` reads chunk
  format natively, so no chunk-level parsing is required.

### Documentation

- New "Why Files, Not Images" section in `docs/geode-design.md`
  rebutting the standard "Smalltalk is different" objections.
- New "Why git, not OCI" section explaining the choice to distribute
  via git rather than OCI artifacts.
- Documented conditional dependencies, TFILE loading, and `.mcz`
  migration in both the design doc and the README.
- Renamed `docs/gspm-design.md` → `docs/geode-design.md`.

## 0.1.1 — 2026-02-28

### Changed

- Renamed PyPI package from `gspm` to `gemstone-gspm` to avoid conflict with
  an existing package. The CLI command remains `gspm`.
- Repository URL updated to `https://github.com/jgfoster/gspm`.
- Added `[project.urls]` (Homepage, Repository, Issues) to `pyproject.toml`.

### Documentation

- Added PyPI publishing instructions to README.

## 0.1.0 — 2026-02-28

Initial release.

### Features

- **Manifest (`gemstone.toml`)**: Cargo-style project manifest with `[package]`,
  `[load]`, `[dependencies]`, `[dev-dependencies]`, and `[test]` sections.
  Cargo-style version constraints (`^`, `~`, `*`) are expanded to PEP 440 ranges.
- **CLI** with 8 commands: `init`, `add`, `fetch`, `install`, `test`, `update`,
  `tree`, and `publish`.
- **Git-based dependency resolution**: clone, resolve version constraints against
  tags, and lock to exact SHAs in `gemstone.lock`.
- **Topaz script generation**: produces a single load script that files in
  dependencies (topologically ordered) and project code into a GemStone stone.
  Supports `--dry-run` to preview without executing.
- **Conditional loading**: version-gated `[load.conditions]` sections allow
  loading different files for different GemStone versions.
- **Tonel transpilation**: parses Tonel `.class.st` files and generates two-phase
  Topaz scripts (class definitions first, then methods) to eliminate forward
  reference errors. Supports classes, extensions, class-side methods, instance
  variables, class variables, pool dictionaries, and comments.
- **FileTree transpilation**: parses FileTree/Cypress `.package/` directories
  (one `.st` file per method) and generates the same two-phase Topaz output.
  Supports normal and variable (indexable) classes, extensions, class comments,
  and automatic inheritance-based load ordering.
- **Auto-discovery**: when a dependency has no manifest or load overrides, gspm
  recursively searches for Tonel directories and FileTree packages, skipping
  test directories. Falls back to `.gs` files if neither format is found.
- **Load overrides**: dependencies without a `gemstone.toml` can specify
  `files`, `tonel`, or `filetree` lists inline in the manifest to control
  exactly which sources are loaded.
- **Package registry**: lightweight GitHub-based index (`gspm-index`) for
  publishing and discovering packages. `gspm publish` opens a PR via `gh`.
- **Global configuration**: `~/.gspm/config.toml` for registry URL and
  per-stone credentials (user/password).

### Documentation

- `README.md` — project overview, quick start, manifest reference, Tonel
  format guide, command reference, and comparison with Rowan.
- `docs/geode-design.md` — architecture and design decisions.
- `docs/source-formats.md` — guide to the three supported source formats
  (Topaz, Tonel, FileTree) with configuration examples and sample links.

### Samples

- `samples/minimal/` — no dependencies, persistent Counter class.
- `samples/seaside/` — Seaside web app with FileTree deps (Seaside, Grease)
  and a Tonel dep (Magritte).
- `samples/grease/` — Grease portability layer with conditional loading.
- `samples/zinc/` — HTTP client using Zinc via FileTree.
- `samples/magritte-app/` — Magritte metadata framework with conditional
  loading for GemStone 3.6 vs 3.7.
- `samples/rowan-tool/` — Rowan introspection tool with non-standard source
  root.
- `samples/tonel-project/` — TodoApp with own source in Tonel format.

### Tests

- 148 tests covering manifest parsing, version constraint expansion, Tonel
  transpilation, FileTree transpilation, Topaz script generation, dependency
  resolution, lock file handling, and CLI commands.
