"""User and project configuration for gspm."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import tomlkit

from gspm.errors import ConfigError

GLOBAL_CONFIG_DIR = Path.home() / ".gspm"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.toml"

DEFAULT_REGISTRY = "https://github.com/GemTalk/gspm-index"


@dataclass
class StoneConfig:
    """Credentials and connection info for a GemStone stone."""

    name: str
    user: str = "DataCurator"
    password: str = "swordfish"


@dataclass
class GspmConfig:
    """Global gspm configuration."""

    registry_url: str = DEFAULT_REGISTRY
    stones: Dict[str, StoneConfig] = field(default_factory=dict)


def load_config() -> GspmConfig:
    """Load global config from ~/.gspm/config.toml.

    Returns default config if file doesn't exist.
    """
    if not GLOBAL_CONFIG_FILE.exists():
        return GspmConfig()

    try:
        doc = tomlkit.loads(GLOBAL_CONFIG_FILE.read_text())
    except Exception as e:
        raise ConfigError(f"Invalid config file: {e}") from e

    config = GspmConfig(
        registry_url=doc.get("registry_url", DEFAULT_REGISTRY),
    )

    for name, stone_data in doc.get("stones", {}).items():
        config.stones[name] = StoneConfig(
            name=name,
            user=stone_data.get("user", "DataCurator"),
            password=stone_data.get("password", "swordfish"),
        )

    return config


def get_stone_config(stone_name: str, config: Optional[GspmConfig] = None) -> StoneConfig:
    """Get credentials for a named stone.

    Falls back to defaults if not configured.
    """
    if config is None:
        config = load_config()

    return config.stones.get(stone_name, StoneConfig(name=stone_name))
