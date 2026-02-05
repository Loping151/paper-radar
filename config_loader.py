"""Configuration loader with environment variable substitution."""

import os
import re
from pathlib import Path
from typing import Any
import yaml
from dotenv import load_dotenv


def substitute_env_vars(value: Any) -> Any:
    """
    Recursively substitute environment variables in config values.

    Supports ${VAR_NAME} syntax.
    """
    if isinstance(value, str):
        # Find all ${VAR_NAME} patterns
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)

        for var_name in matches:
            env_value = os.getenv(var_name, "")
            value = value.replace(f"${{{var_name}}}", env_value)

        return value

    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]

    return value


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file with environment variable substitution.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dict with env vars substituted
    """
    # Load .env file if exists
    env_file = Path(config_path).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    # Load YAML config
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Substitute environment variables
    config = substitute_env_vars(config)

    return config


def get_llm_config(config: dict, llm_type: str) -> dict:
    """
    Get LLM configuration for a specific type.

    Args:
        config: Full configuration dict
        llm_type: "light", "heavy", or "summary"

    Returns:
        LLM configuration dict ready for BaseLLMClient
    """
    llm_config = config.get("llm", {}).get(llm_type, {})

    # For summary, it may reference light or heavy
    if llm_type == "summary":
        use = llm_config.get("use", "light")
        base_config = config.get("llm", {}).get(use, {}).copy()
        # Override with summary-specific settings
        base_config["temperature"] = llm_config.get("temperature", base_config.get("temperature", 0.5))
        base_config["max_tokens"] = llm_config.get("max_tokens", base_config.get("max_tokens", 2000))
        return base_config

    return llm_config
