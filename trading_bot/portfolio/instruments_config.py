"""
Trading Instruments Configuration

Defines all tradeable instruments and their specific trading windows.
All times are in GMT (will be automatically adjusted for GMT+1/BST).

Trading Windows per Instrument:
- EUR/USD & GBP/USD: Multiple optimal windows based on historical analysis
  - Mean Reversion: 05:00-13:00 (covers hours 5,6,7,9,12)
  - Breakout: 03:00-17:00 (covers hours 3,14,15,16)
"""

from datetime import time
from typing import Dict, List, Any


# Instrument configuration dictionary
INSTRUMENTS = {
    # EUR/USD
    'EURUSD': {
        'name': 'EUR/USD',
        'symbol': 'EURUSD',
        'enabled': True,
        # Recovery settings for EURUSD (~60-80 pip daily range)
        'recovery': {
            'grid_spacing_pips': 12,      # Grid every 12 pips
            'dca_trigger_pips': 30,       # DCA after 30 pips
            'hedge_trigger_pips': 45,     # Hedge after 45 pips
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        # Take profit settings
        'take_profit': {
            'partial_1_pips': 12,         # 25% close at 12 pips
            'partial_1_percent': 0.25,
            'partial_2_pips': 25,         # 50% close at 25 pips
            'partial_2_percent': 0.50,
            'full_tp_pips': 40,           # Close all at 40 pips
            'vwap_exit_enabled': True,
        },
        'windows': [
            {
                'name': 'All-Day Trading Window',
                'start': time(0, 0),     # 00:00 GMT (midnight)
                'end': time(23, 59),     # 23:59 GMT (end of day)
                'strategy_type': 'mixed',
                'description': 'Combined mean reversion and breakout strategies with time filters',
                'close_all_at_end': False,  # Don't force close - let strategies manage
                'min_confluence_score': 4,
            }
        ]
    },

    # GBP/USD
    'GBPUSD': {
        'name': 'GBP/USD',
        'symbol': 'GBPUSD',
        'enabled': True,
        # Recovery settings for GBPUSD (~100-120 pip daily range - more volatile than EURUSD)
        'recovery': {
            'grid_spacing_pips': 18,      # Grid every 18 pips (wider than EURUSD)
            'dca_trigger_pips': 40,       # DCA after 40 pips
            'hedge_trigger_pips': 55,     # Hedge after 55 pips
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        # Take profit settings
        'take_profit': {
            'partial_1_pips': 18,         # 25% close at 18 pips
            'partial_1_percent': 0.25,
            'partial_2_pips': 35,         # 50% close at 35 pips
            'partial_2_percent': 0.50,
            'full_tp_pips': 55,           # Close all at 55 pips
            'vwap_exit_enabled': True,
        },
        'windows': [
            {
                'name': 'All-Day Trading Window',
                'start': time(0, 0),     # 00:00 GMT (midnight)
                'end': time(23, 59),     # 23:59 GMT (end of day)
                'strategy_type': 'mixed',
                'description': 'Combined mean reversion and breakout strategies with time filters',
                'close_all_at_end': False,  # Don't force close - let strategies manage
                'min_confluence_score': 4,
            }
        ]
    },
}


def get_instruments_config() -> Dict[str, Any]:
    """
    Get the instruments configuration.

    Returns:
        Dictionary of instrument configurations
    """
    return INSTRUMENTS


def get_enabled_instruments() -> List[str]:
    """
    Get list of enabled instrument symbols.

    Returns:
        List of enabled instrument symbols
    """
    return [symbol for symbol, config in INSTRUMENTS.items() if config.get('enabled', True)]


def get_instrument_config(symbol: str) -> Dict[str, Any]:
    """
    Get configuration for a specific instrument.

    Args:
        symbol: Instrument symbol

    Returns:
        Instrument configuration dictionary

    Raises:
        KeyError: If instrument not found
    """
    if symbol not in INSTRUMENTS:
        raise KeyError(f"Instrument '{symbol}' not found in configuration")

    return INSTRUMENTS[symbol]


def is_instrument_enabled(symbol: str) -> bool:
    """
    Check if an instrument is enabled for trading.

    Args:
        symbol: Instrument symbol

    Returns:
        True if enabled, False otherwise
    """
    return INSTRUMENTS.get(symbol, {}).get('enabled', False)


def get_recovery_settings(symbol: str) -> Dict[str, Any]:
    """
    Get recovery settings for a specific instrument.

    Args:
        symbol: Instrument symbol

    Returns:
        Dictionary with recovery settings (grid_spacing_pips, dca_trigger_pips, etc.)

    Raises:
        KeyError: If instrument not found or has no recovery settings
    """
    if symbol not in INSTRUMENTS:
        raise KeyError(f"Instrument '{symbol}' not found in configuration")

    if 'recovery' not in INSTRUMENTS[symbol]:
        raise KeyError(f"Instrument '{symbol}' has no recovery settings configured")

    return INSTRUMENTS[symbol]['recovery']


def get_take_profit_settings(symbol: str) -> Dict[str, Any]:
    """
    Get take profit settings for a specific instrument.

    Args:
        symbol: Instrument symbol

    Returns:
        Dictionary with take profit settings (partial_1_pips, partial_2_pips, etc.)

    Raises:
        KeyError: If instrument not found or has no take profit settings
    """
    if symbol not in INSTRUMENTS:
        raise KeyError(f"Instrument '{symbol}' not found in configuration")

    if 'take_profit' not in INSTRUMENTS[symbol]:
        raise KeyError(f"Instrument '{symbol}' has no take profit settings configured")

    return INSTRUMENTS[symbol]['take_profit']


def get_instruments_by_strategy_type(strategy_type: str) -> List[str]:
    """
    Get instruments that use a specific strategy type.

    Args:
        strategy_type: Strategy type (e.g., 'reversal', 'correction', 'fade', 'settling')

    Returns:
        List of instrument symbols
    """
    result = []
    for symbol, config in INSTRUMENTS.items():
        if not config.get('enabled', True):
            continue

        for window in config.get('windows', []):
            if window.get('strategy_type') == strategy_type:
                result.append(symbol)
                break

    return result


# Validation function
def validate_configuration() -> List[str]:
    """
    Validate the instruments configuration.

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    for symbol, config in INSTRUMENTS.items():
        # Check required fields
        if 'symbol' not in config:
            errors.append(f"{symbol}: Missing 'symbol' field")
        if 'windows' not in config:
            errors.append(f"{symbol}: Missing 'windows' field")
            continue

        # Check windows
        for i, window in enumerate(config['windows']):
            if 'start' not in window:
                errors.append(f"{symbol} window {i}: Missing 'start' time")
            if 'end' not in window:
                errors.append(f"{symbol} window {i}: Missing 'end' time")
            if 'strategy_type' not in window:
                errors.append(f"{symbol} window {i}: Missing 'strategy_type'")

            # Check time validity
            if 'start' in window and 'end' in window:
                start = window['start']
                end = window['end']
                if not isinstance(start, time) or not isinstance(end, time):
                    errors.append(f"{symbol} window {i}: start/end must be time objects")

    return errors


# Run validation on import
_validation_errors = validate_configuration()
if _validation_errors:
    import warnings
    warnings.warn(f"Instruments configuration has errors: {_validation_errors}")


if __name__ == "__main__":
    print("=== Instruments Configuration Test ===\n")

    print(f"Total instruments: {len(INSTRUMENTS)}")
    print(f"Enabled instruments: {len(get_enabled_instruments())}")

    print("\nInstruments by strategy type:")
    for strategy in ['reversal', 'correction', 'fade', 'settling']:
        instruments = get_instruments_by_strategy_type(strategy)
        print(f"  {strategy}: {instruments}")

    print("\nDetailed configuration:")
    for symbol, config in INSTRUMENTS.items():
        print(f"\n{config['name']} ({symbol}):")
        print(f"  Enabled: {config.get('enabled', True)}")
        for window in config.get('windows', []):
            print(f"  Window: {window['name']}")
            print(f"    Time: {window['start']} - {window['end']}")
            print(f"    Strategy: {window['strategy_type']}")
            print(f"    Close negatives: {window['close_negatives_at_end']}")

    # Validation
    errors = validate_configuration()
    if errors:
        print(f"\n❌ Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"\n✓ Configuration is valid")
