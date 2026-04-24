"""Core data models for gspm."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PackageMetadata:
    """The [package] section of gemstone.toml."""

    name: str
    version: str
    description: str = ""
    gemstone: str = ""  # GemStone version constraint, e.g., ">=3.5"
    authors: List[str] = field(default_factory=list)
    license: str = ""
    repository: str = ""


@dataclass
class LoadSpec:
    """The [load] section: which files to load and in what order."""

    files: List[str] = field(default_factory=list)
    tonel: List[str] = field(default_factory=list)
    filetree: List[str] = field(default_factory=list)
    conditions: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class Dependency:
    """A single dependency declaration from gemstone.toml."""

    name: str
    version: str  # version constraint string, e.g., "^2.0"
    git: str = ""  # git URL
    files: List[str] = field(default_factory=list)  # load override: .gs files
    tonel: List[str] = field(default_factory=list)  # load override: Tonel dirs
    filetree: List[str] = field(default_factory=list)  # load override: FileTree packages


@dataclass
class SuiteSpec:
    """The [test] section."""

    files: List[str] = field(default_factory=list)


@dataclass
class ConditionalDeps:
    """A block of dependencies that only apply under a specific condition.

    ``dimension`` is the conditional axis ("gemstone" or "platform").
    ``spec`` is the per-dimension predicate — a PEP 440 specifier like
    ">=3.7" for the "gemstone" dimension, or a platform name like "linux"
    for the "platform" dimension. ``deps`` is the set of dependencies
    activated when the condition matches.
    """

    dimension: str
    spec: str
    deps: Dict[str, "Dependency"] = field(default_factory=dict)


@dataclass
class Manifest:
    """Complete parsed gemstone.toml."""

    package: PackageMetadata
    load: LoadSpec = field(default_factory=LoadSpec)
    dependencies: Dict[str, Dependency] = field(default_factory=dict)
    dev_dependencies: Dict[str, Dependency] = field(default_factory=dict)
    conditional_dependencies: List[ConditionalDeps] = field(default_factory=list)
    conditional_dev_dependencies: List[ConditionalDeps] = field(default_factory=list)
    test: SuiteSpec = field(default_factory=SuiteSpec)


@dataclass
class ResolvedPackage:
    """A single entry in gemstone.lock."""

    name: str
    version: str
    source: str  # "git+https://..."
    sha: str
    dependencies: List[str] = field(default_factory=list)


@dataclass
class Lockfile:
    """Complete parsed gemstone.lock."""

    packages: List[ResolvedPackage] = field(default_factory=list)

    def find(self, name: str) -> Optional[ResolvedPackage]:
        """Look up a package by name."""
        for pkg in self.packages:
            if pkg.name == name:
                return pkg
        return None


@dataclass
class RegistryEntry:
    """A package listing in the registry index."""

    name: str
    git: str
    versions: List[str] = field(default_factory=list)
    description: str = ""
