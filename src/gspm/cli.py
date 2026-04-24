"""gspm CLI — GemStone Package Manager."""

import sys
from pathlib import Path
from typing import Optional

import click

from gspm import __version__
from gspm.errors import GspmError


def _detect_platform() -> str:
    """Map ``sys.platform`` to a stable platform name for conditional deps."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return sys.platform


@click.group()
@click.version_option(version=__version__, prog_name="gspm")
def main() -> None:
    """GemStone Package Manager — manage GemStone/S packages with Git."""


# ---------------------------------------------------------------------------
# gspm init
# ---------------------------------------------------------------------------


@main.command()
@click.argument("name", required=False)
def init(name: Optional[str]) -> None:
    """Create a new project with a skeleton gemstone.toml."""
    from gspm.manifest import scaffold_manifest

    if name:
        project_dir = Path.cwd() / name
        project_dir.mkdir(parents=True, exist_ok=True)
    else:
        project_dir = Path.cwd()
        if not name:
            name = project_dir.name

    manifest_path = project_dir / "gemstone.toml"
    if manifest_path.exists():
        click.secho("gemstone.toml already exists.", fg="yellow")
        return

    # Create directory structure
    (project_dir / "src").mkdir(exist_ok=True)
    (project_dir / "tests").mkdir(exist_ok=True)

    # Write manifest
    manifest_path.write_text(scaffold_manifest(name))

    # Write .gitignore if it doesn't exist
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# gspm working directories\n.gspm/\n")

    click.secho(f"Created new gspm project: {name}", fg="green")
    click.echo(f"  {manifest_path}")


# ---------------------------------------------------------------------------
# gspm add
# ---------------------------------------------------------------------------


@main.command()
@click.argument("package")
@click.option("--version", "-v", "version_spec", default="*", help="Version constraint")
@click.option("--git", "git_url", default="", help="Git URL for the package")
@click.option("--dev", is_flag=True, help="Add as a dev-dependency")
@click.option("--files", multiple=True, help="Load override: .gs files (repeatable)")
@click.option("--tonel", multiple=True, help="Load override: Tonel directories (repeatable)")
@click.option("--filetree", multiple=True, help="Load override: FileTree .package dirs (repeatable)")
def add(
    package: str,
    version_spec: str,
    git_url: str,
    dev: bool,
    files: tuple,
    tonel: tuple,
    filetree: tuple,
) -> None:
    """Add a dependency to gemstone.toml."""
    from gspm.manifest import add_dependency
    from gspm.registry import resolve_git_url
    from gspm.models import Dependency

    manifest_path = Path.cwd() / "gemstone.toml"
    if not manifest_path.exists():
        _error("No gemstone.toml found. Run 'gspm init' first.")

    # Resolve git URL from registry if not provided
    if not git_url:
        try:
            dep = Dependency(name=package, version=version_spec)
            git_url = resolve_git_url(package, dep)
        except GspmError:
            _error(
                f"Package '{package}' not found in registry. "
                f"Specify a git URL with --git."
            )

    try:
        add_dependency(
            manifest_path,
            package,
            version_spec,
            git=git_url,
            dev=dev,
            files=list(files) if files else None,
            tonel=list(tonel) if tonel else None,
            filetree=list(filetree) if filetree else None,
        )
    except GspmError as e:
        _error(str(e))

    section = "dev-dependencies" if dev else "dependencies"
    click.secho(f"Added {package} to [{section}]", fg="green")


# ---------------------------------------------------------------------------
# gspm fetch
# ---------------------------------------------------------------------------


@main.command()
@click.option("--gs-version", default=None,
              help="GemStone version to activate gemstone-conditional dependencies")
def fetch(gs_version: Optional[str]) -> None:
    """Resolve all dependencies and update gemstone.lock."""
    from gspm.manifest import load_manifest
    from gspm.lockfile import save_lockfile
    from gspm.resolver import PackageSource, Resolver
    from gspm import cache
    from gspm import git as git_ops

    project_root = Path.cwd()
    manifest_path = project_root / "gemstone.toml"
    if not manifest_path.exists():
        _error("No gemstone.toml found. Run 'gspm init' first.")

    try:
        manifest = load_manifest(manifest_path)
    except GspmError as e:
        _error(str(e))

    has_any_deps = (
        manifest.dependencies or manifest.dev_dependencies
        or manifest.conditional_dependencies
        or manifest.conditional_dev_dependencies
    )
    if not has_any_deps:
        click.echo("No dependencies declared.")
        return

    click.echo("Resolving dependencies...")

    try:
        source = PackageSource(project_root)
        resolver = Resolver(source)
        lockfile = resolver.resolve(
            manifest,
            gemstone_version=gs_version,
            platform=_detect_platform(),
        )
    except GspmError as e:
        _error(str(e))

    # Save lockfile
    lock_path = project_root / "gemstone.lock"
    save_lockfile(lockfile, lock_path)
    click.echo(f"Wrote {lock_path.name}")

    # Cache resolved packages
    click.echo("Fetching packages...")
    cache.ensure_dirs(project_root)

    for pkg in lockfile.packages:
        if cache.is_cached(project_root, pkg.sha):
            click.echo(f"  {pkg.name} {pkg.version} (cached)")
            continue

        click.echo(f"  {pkg.name} {pkg.version}")
        git_url = pkg.source.replace("git+", "", 1)
        bare_path = cache.bare_repo_path(project_root, pkg.name)
        git_ops.clone_bare(git_url, bare_path)
        dest = cache.cache_path(project_root, pkg.sha)
        git_ops.checkout_tree(bare_path, pkg.sha, dest)

    # Populate deps
    cache.populate_deps(project_root, lockfile)
    click.secho(
        f"Fetched {len(lockfile.packages)} package(s).", fg="green"
    )


# ---------------------------------------------------------------------------
# gspm install
# ---------------------------------------------------------------------------


@main.command()
@click.argument("stone")
@click.option("--user", default=None, help="GemStone user (overrides config)")
@click.option("--password", default=None, help="GemStone password (overrides config)")
@click.option("--gs-version", default=None, help="GemStone version for conditional loading")
@click.option("--dry-run", is_flag=True, help="Print the Topaz script without running it")
@click.option("--tfile", "use_tfile", is_flag=True,
              help="Load Tonel via Topaz TFILE instead of transpiling to .tpz "
                   "(requires a stone with TFILE support; falls back to transpile "
                   "when peer-class forward references are detected)")
def install(
    stone: str,
    user: Optional[str],
    password: Optional[str],
    gs_version: Optional[str],
    dry_run: bool,
    use_tfile: bool,
) -> None:
    """Generate and run a Topaz script to load code into STONE."""
    from gspm.manifest import load_manifest
    from gspm.lockfile import load_lockfile
    from gspm.config import get_stone_config
    from gspm.topaz import generate_install_script, run_topaz

    project_root = Path.cwd()
    manifest, lockfile = _load_project(project_root)

    stone_cfg = get_stone_config(stone)
    script = generate_install_script(
        project_root=project_root,
        manifest=manifest,
        lockfile=lockfile,
        stone_name=stone,
        user=user or stone_cfg.user,
        password=password or stone_cfg.password,
        gemstone_version=gs_version,
        use_tfile=use_tfile,
    )

    if dry_run:
        click.echo(script)
        return

    click.echo(f"Loading into stone '{stone}'...")
    try:
        output = run_topaz(script, project_root)
        click.echo(output)
        click.secho("Install complete.", fg="green")
    except GspmError as e:
        _error(str(e))


# ---------------------------------------------------------------------------
# gspm test
# ---------------------------------------------------------------------------


@main.command()
@click.argument("stone")
@click.option("--user", default=None, help="GemStone user (overrides config)")
@click.option("--password", default=None, help="GemStone password (overrides config)")
@click.option("--gs-version", default=None, help="GemStone version for conditional loading")
@click.option("--dry-run", is_flag=True, help="Print the Topaz script without running it")
@click.option("--tfile", "use_tfile", is_flag=True,
              help="Load Tonel via Topaz TFILE instead of transpiling to .tpz")
def test(
    stone: str,
    user: Optional[str],
    password: Optional[str],
    gs_version: Optional[str],
    dry_run: bool,
    use_tfile: bool,
) -> None:
    """Load code including dev-dependencies and run tests in STONE."""
    from gspm.manifest import load_manifest
    from gspm.lockfile import load_lockfile
    from gspm.config import get_stone_config
    from gspm.topaz import generate_install_script, run_topaz

    project_root = Path.cwd()
    manifest, lockfile = _load_project(project_root)

    stone_cfg = get_stone_config(stone)
    script = generate_install_script(
        project_root=project_root,
        manifest=manifest,
        lockfile=lockfile,
        stone_name=stone,
        user=user or stone_cfg.user,
        password=password or stone_cfg.password,
        gemstone_version=gs_version,
        include_dev=True,
        include_tests=True,
        use_tfile=use_tfile,
    )

    if dry_run:
        click.echo(script)
        return

    click.echo(f"Running tests in stone '{stone}'...")
    try:
        output = run_topaz(script, project_root)
        click.echo(output)
        click.secho("Tests complete.", fg="green")
    except GspmError as e:
        _error(str(e))


# ---------------------------------------------------------------------------
# gspm update
# ---------------------------------------------------------------------------


@main.command()
@click.argument("package", required=False)
@click.option("--gs-version", default=None,
              help="GemStone version to activate gemstone-conditional dependencies")
def update(package: Optional[str], gs_version: Optional[str]) -> None:
    """Update dependencies within declared constraints."""
    from gspm.manifest import load_manifest
    from gspm.lockfile import load_lockfile, save_lockfile
    from gspm.resolver import PackageSource, Resolver
    from gspm import cache
    from gspm import git as git_ops

    project_root = Path.cwd()
    manifest_path = project_root / "gemstone.toml"
    if not manifest_path.exists():
        _error("No gemstone.toml found. Run 'gspm init' first.")

    try:
        manifest = load_manifest(manifest_path)
    except GspmError as e:
        _error(str(e))

    click.echo("Resolving dependencies...")

    try:
        source = PackageSource(project_root)
        resolver = Resolver(source)
        lockfile = resolver.resolve(
            manifest,
            gemstone_version=gs_version,
            platform=_detect_platform(),
        )
    except GspmError as e:
        _error(str(e))

    # Save lockfile
    lock_path = project_root / "gemstone.lock"
    save_lockfile(lockfile, lock_path)

    # Fetch any new SHAs
    cache.ensure_dirs(project_root)
    for pkg in lockfile.packages:
        if not cache.is_cached(project_root, pkg.sha):
            click.echo(f"  Fetching {pkg.name} {pkg.version}")
            git_url = pkg.source.replace("git+", "", 1)
            bare_path = cache.bare_repo_path(project_root, pkg.name)
            git_ops.clone_bare(git_url, bare_path)
            dest = cache.cache_path(project_root, pkg.sha)
            git_ops.checkout_tree(bare_path, pkg.sha, dest)

    cache.populate_deps(project_root, lockfile)
    click.secho("Update complete.", fg="green")


# ---------------------------------------------------------------------------
# gspm tree
# ---------------------------------------------------------------------------


@main.command()
def tree() -> None:
    """Display the resolved dependency tree."""
    from gspm.lockfile import load_lockfile

    project_root = Path.cwd()
    lock_path = project_root / "gemstone.lock"
    if not lock_path.exists():
        _error("No gemstone.lock found. Run 'gspm fetch' first.")

    lockfile = load_lockfile(lock_path)
    if not lockfile.packages:
        click.echo("No dependencies.")
        return

    pkg_map = {p.name: p for p in lockfile.packages}

    # Find root packages (not depended on by anyone)
    all_deps = set()
    for pkg in lockfile.packages:
        all_deps.update(pkg.dependencies)

    roots = [p for p in lockfile.packages if p.name not in all_deps]
    if not roots:
        roots = lockfile.packages  # Fallback: show all

    for i, root in enumerate(roots):
        _print_tree(root, pkg_map, prefix="", is_last=(i == len(roots) - 1))


def _print_tree(pkg, pkg_map, prefix="", is_last=True):
    """Recursively print a dependency tree."""
    connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
    if prefix:
        click.echo(f"{prefix}{connector}{pkg.name} {pkg.version}")
    else:
        click.echo(f"{pkg.name} {pkg.version}")

    child_prefix = prefix + ("    " if is_last else "\u2502   ")
    deps = [pkg_map[d] for d in pkg.dependencies if d in pkg_map]

    for j, dep in enumerate(deps):
        _print_tree(dep, pkg_map, prefix=child_prefix, is_last=(j == len(deps) - 1))


# ---------------------------------------------------------------------------
# gspm publish
# ---------------------------------------------------------------------------


@main.command()
def publish() -> None:
    """Publish this package to the registry."""
    from gspm.manifest import load_manifest
    from gspm.registry import publish_package

    project_root = Path.cwd()
    manifest_path = project_root / "gemstone.toml"
    if not manifest_path.exists():
        _error("No gemstone.toml found.")

    try:
        manifest = load_manifest(manifest_path)
    except GspmError as e:
        _error(str(e))

    click.echo(
        f"Publishing {manifest.package.name} {manifest.package.version}..."
    )

    try:
        pr_url = publish_package(manifest, project_root)
        click.secho("Published!", fg="green")
        click.echo(f"PR: {pr_url}")
    except GspmError as e:
        _error(str(e))


# ---------------------------------------------------------------------------
# gspm migrate-mcz
# ---------------------------------------------------------------------------


@main.command(name="migrate-mcz")
@click.argument("mcz_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_dir", type=click.Path(),
              help="Output directory (defaults to a sibling of the .mcz file "
                   "named after the package)")
def migrate_mcz_cmd(mcz_path: str, out_dir: Optional[str]) -> None:
    """Convert a Monticello .mcz package to a gspm package directory.

    Best-effort migration: the .mcz source is repackaged as Topaz file-in
    format with Monticello stamp metadata stripped. Complex packages
    (traits, unusual extensions) may need manual review of the output.
    """
    from gspm.mcz import migrate_mcz

    mcz = Path(mcz_path).resolve()
    out = Path(out_dir).resolve() if out_dir else mcz.parent / mcz.stem

    try:
        manifest_path = migrate_mcz(mcz, out)
    except GspmError as e:
        _error(str(e))

    click.secho(f"Migrated {mcz.name} → {out}", fg="green")
    click.echo(f"  {manifest_path}")
    click.echo("Review gemstone.toml and the generated .gs file before use.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_project(project_root):
    """Load manifest and lockfile, or exit with error."""
    from gspm.manifest import load_manifest
    from gspm.lockfile import load_lockfile

    manifest_path = project_root / "gemstone.toml"
    lock_path = project_root / "gemstone.lock"

    if not manifest_path.exists():
        _error("No gemstone.toml found. Run 'gspm init' first.")
    if not lock_path.exists():
        _error("No gemstone.lock found. Run 'gspm fetch' first.")

    try:
        manifest = load_manifest(manifest_path)
        lockfile = load_lockfile(lock_path)
    except GspmError as e:
        _error(str(e))

    return manifest, lockfile


def _error(message: str) -> None:
    """Print error message and exit."""
    click.secho(f"Error: {message}", fg="red", err=True)
    sys.exit(1)
