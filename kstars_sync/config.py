"""
Configuration handling for kstars-sync.

Configuration precedence (highest first):

1. Command-line arguments
2. ~/.config/kstars-sync/config.ini
3. Built-in defaults
"""

from __future__ import annotations

import argparse
import configparser
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "kstars-sync"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.ini"


@dataclass(slots=True)
class Config:
    """Application configuration."""

    repo: Path
    kstars: Path
    continue_without_fetch: bool
    dry_run: bool
    verbose: bool


class ConfigError(Exception):
    """Raised when the configuration itself is invalid."""


class RuntimeValidationError(Exception):
    """Raised when the runtime environment is unsuitable."""


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the application's argument parser."""

    parser = argparse.ArgumentParser(
        prog="kstars-sync",
        description="Synchronise a KStars Git repository before and after running KStars.",
    )

    parser.add_argument(
        "--repo",
        type=Path,
        help="Path to the Git repository (defaults to the script directory).",
    )

    parser.add_argument(
        "--kstars",
        type=Path,
        help="Path to the KStars executable (default: /usr/bin/kstars).",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_FILE,
        help="Configuration file.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )

    return parser


def load_config(argv: Optional[list[str]] = None) -> Config:
    """
    Load configuration.

    Precedence:
        defaults < config.ini < command line
    """

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    defaults = {
        "repo": Path(__file__).resolve().parent,
        "kstars": Path("/usr/bin/kstars"),
        "continue_without_fetch": False,
    }

    file_values = _load_config_file(args.config)

    repo = args.repo or file_values.get("repo") or defaults["repo"]
    kstars = args.kstars or file_values.get("kstars") or defaults["kstars"]

    continue_without_fetch = file_values.get(
        "continue_without_fetch",
        defaults["continue_without_fetch"],
    )

    return Config(
        repo=repo.expanduser().resolve(),
        kstars=kstars.expanduser().resolve(),
        continue_without_fetch=continue_without_fetch,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def validate_config(config: Config) -> None:
    """Validate the configuration."""

    if not config.repo.exists():
        raise ConfigError(f"Repository does not exist: {config.repo}")

    if not config.repo.is_dir():
        raise ConfigError(f"Repository is not a directory: {config.repo}")

    git_dir = config.repo / ".git"

    if not git_dir.exists():
        raise ConfigError(f"{config.repo} is not a Git repository.")

    if not config.kstars.exists():
        raise ConfigError(f"KStars executable not found: {config.kstars}")

    if not config.kstars.is_file():
        raise ConfigError(f"KStars path is not a file: {config.kstars}")


def validate_runtime() -> None:
    """Validate the runtime environment."""

    if shutil.which("git") is None:
        raise RuntimeValidationError(
            "'git' executable was not found in PATH."
        )


def _load_config_file(path: Path) -> dict:
    """
    Load config.ini.

    Missing configuration files are not an error.
    """

    if not path.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.read(path)

    values = {}

    if parser.has_section("general"):
        section = parser["general"]

        if "repo" in section:
            values["repo"] = Path(section["repo"])

        if "continue_without_fetch" in section:
            values["continue_without_fetch"] = section.getboolean(
                "continue_without_fetch"
            )

    if parser.has_section("kstars"):
        section = parser["kstars"]

        if "path" in section:
            values["kstars"] = Path(section["path"])

    return values

