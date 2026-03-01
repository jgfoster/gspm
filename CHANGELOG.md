# Changelog

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
- `docs/gspm-design.md` — architecture and design decisions.
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
