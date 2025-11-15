"""
Gameplay Configuration Loader (S2-07)

Loads and provides access to centralized gameplay configuration from JSON file.
Supports nested config keys with dot notation (e.g., "snapshots.frequency").
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GameplayConfig:
    """
    Centralized gameplay configuration manager.

    Loads configuration from gameplay.json file and provides
    convenient access via get() method with dot notation support.

    Example:
        config = GameplayConfig.load()
        freq = config.get("snapshots.frequency", default=60)
    """

    def __init__(self, config_data: dict[str, Any]):
        """
        Initialize config with loaded data.

        Args:
            config_data: Dictionary containing configuration
        """
        self._config = config_data
        self._access_log: set[str] = set()  # Track accessed keys

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with optional default.

        Supports dot notation for nested keys (e.g., "snapshots.frequency").

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default if not found
        """
        # Track that this key was accessed
        self._access_log.add(key)

        # Split key by dots for nested access
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Key not found - log warning and return default
                logger.warning(
                    f"Config key '{key}' not found, using default: {default}"
                )
                return default

        return value

    def get_all(self) -> dict[str, Any]:
        """
        Get the entire configuration dictionary.

        Returns:
            Full configuration dict
        """
        return self._config.copy()

    def get_accessed_keys(self) -> set[str]:
        """
        Get set of all keys that have been accessed via get().

        Useful for debugging and understanding config usage.

        Returns:
            Set of accessed configuration keys
        """
        return self._access_log.copy()

    @classmethod
    def load(cls, config_path: Path | None = None) -> "GameplayConfig":
        """
        Load gameplay configuration from JSON file.

        Args:
            config_path: Path to config file (defaults to backend/config/gameplay.json)

        Returns:
            GameplayConfig instance with loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if config_path is None:
            # Default path: backend/config/gameplay.json
            # Resolve relative to this file's location
            module_dir = Path(__file__).parent
            config_path = module_dir.parent.parent / "config" / "gameplay.json"

        logger.info(f"Loading gameplay config from: {config_path}")

        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        logger.info(f"Loaded gameplay config version: {config_data.get('version', 'unknown')}")

        return cls(config_data)

    @classmethod
    def load_with_fallback(cls, config_path: Path | None = None) -> "GameplayConfig":
        """
        Load configuration with fallback to defaults if file missing.

        If config file doesn't exist, returns config with sensible defaults
        instead of raising an error.

        Args:
            config_path: Path to config file

        Returns:
            GameplayConfig instance
        """
        try:
            return cls.load(config_path)
        except FileNotFoundError:
            logger.warning(
                "Config file not found, using built-in defaults"
            )
            return cls(_get_default_config())


def _get_default_config() -> dict[str, Any]:
    """
    Get default configuration values.

    These are fallback values if gameplay.json is missing.

    Returns:
        Dictionary with default configuration
    """
    return {
        "version": "1.0.0-defaults",
        "snapshots": {
            "frequency": 60,
        },
        "events": {
            "enable_persistence": True,
            "batch_size": 1000,
        },
        "action_commands": {
            "max_per_tick": 100,
            "max_queue_size": 1000,
            "default_expiry_ticks": 10,
        },
        "economy": {
            "base_production_rate": 1.0,
            "trade_multiplier": 1.5,
            "prosperity_decay_rate": 0.01,
        },
        "politics": {
            "unrest_threshold": 75,
            "rebellion_chance_per_tick": 0.05,
        },
        "tick_system": {
            "max_duration_warning_ms": 1000,
        },
    }


# Global config instance (loaded at app startup)
_global_config: GameplayConfig | None = None


def get_gameplay_config() -> GameplayConfig:
    """
    Get the global gameplay configuration instance.

    Config is loaded once at app startup and cached.

    Returns:
        Global GameplayConfig instance

    Raises:
        RuntimeError: If config hasn't been loaded yet
    """
    global _global_config
    if _global_config is None:
        raise RuntimeError(
            "Gameplay config not loaded. Call init_gameplay_config() at app startup."
        )
    return _global_config


def init_gameplay_config(config_path: Path | None = None) -> GameplayConfig:
    """
    Initialize the global gameplay configuration.

    Should be called once at app startup.

    Args:
        config_path: Optional path to config file

    Returns:
        Loaded GameplayConfig instance
    """
    global _global_config
    _global_config = GameplayConfig.load_with_fallback(config_path)
    logger.info("Gameplay config initialized successfully")
    return _global_config
