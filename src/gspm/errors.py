"""gspm exception hierarchy."""


class GspmError(Exception):
    """Base exception for all gspm errors."""


class ManifestError(GspmError):
    """Error parsing or validating gemstone.toml."""


class LockfileError(GspmError):
    """Error parsing or validating gemstone.lock."""


class ResolverError(GspmError):
    """Dependency resolution failed."""


class GitError(GspmError):
    """A git subprocess operation failed."""


class CacheError(GspmError):
    """Error managing .gspm/cache or .gspm/deps."""


class RegistryError(GspmError):
    """Error communicating with the package registry."""


class TopazError(GspmError):
    """Error generating or running a Topaz script."""


class ConfigError(GspmError):
    """Error in user/project configuration."""


class TonelError(GspmError):
    """Error parsing a Tonel .st file."""


class FileTreeError(GspmError):
    """Error parsing a FileTree .package directory."""


class MczError(GspmError):
    """Error reading or migrating a Monticello .mcz archive."""
