"""
Utility Functions
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any
import sys


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def load_credentials(cred_path: str = "config/mt5_credentials.yaml") -> Dict[str, Any]:
    """
    Load MT5 credentials from YAML file

    Args:
        cred_path: Path to credentials file

    Returns:
        Credentials dictionary
    """
    cred_file = Path(cred_path)

    if not cred_file.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {cred_path}\n"
            "Please run the account setup GUI: python src/gui/account_setup.py"
        )

    with open(cred_file, 'r') as f:
        credentials = yaml.safe_load(f)

    return credentials.get('mt5', {})


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """
    Setup logging configuration

    Args:
        config: Configuration dictionary

    Returns:
        Configured logger
    """
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file_path', 'logs/mt5_bot.log')
    max_bytes = log_config.get('max_bytes', 10485760)
    backup_count = log_config.get('backup_count', 5)
    console_output = log_config.get('console_output', True)

    # Ensure logs directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level))

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level))
        logger.addHandler(console_handler)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    if console_output:
        console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


def format_timeframe(timeframe: str) -> str:
    """
    Format timeframe string to MT5 format

    Args:
        timeframe: Timeframe string (e.g., '1H', 'H1', '15M', 'M15')

    Returns:
        Standardized timeframe string
    """
    tf_map = {
        '1': 'M1', 'M1': 'M1', '1M': 'M1',
        '5': 'M5', 'M5': 'M5', '5M': 'M5',
        '15': 'M15', 'M15': 'M15', '15M': 'M15',
        '30': 'M30', 'M30': 'M30', '30M': 'M30',
        '60': 'H1', 'H1': 'H1', '1H': 'H1',
        '240': 'H4', 'H4': 'H4', '4H': 'H4',
        'D': 'D1', 'D1': 'D1', '1D': 'D1',
        'W': 'W1', 'W1': 'W1', '1W': 'W1',
        'M': 'MN1', 'MN': 'MN1', 'MN1': 'MN1'
    }

    return tf_map.get(timeframe.upper(), timeframe)
