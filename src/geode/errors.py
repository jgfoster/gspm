"""geode exception hierarchy."""


class GeodeError(Exception):
    """Base exception for all geode errors."""


class ManifestError(GeodeError):
    """Error parsing or validating gemstone.toml."""


class LockfileError(GeodeError):
    """Error parsing or validating gemstone.lock."""


class ResolverError(GeodeError):
    """Dependency resolution failed."""


class GitError(GeodeError):
    """A git subprocess operation failed."""


class CacheError(GeodeError):
    """Error managing .geode/cache or .geode/deps."""


class RegistryError(GeodeError):
    """Error communicating with the package registry."""


class TopazError(GeodeError):
    """Error generating or running a Topaz script."""


class ConfigError(GeodeError):
    """Error in user/project configuration."""


class TonelError(GeodeError):
    """Error parsing a Tonel .st file."""


class FileTreeError(GeodeError):
    """Error parsing a FileTree .package directory."""


class MczError(GeodeError):
    """Error reading or migrating a Monticello .mcz archive."""
