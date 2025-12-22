"""
Trading Instruments Configuration

Defines all tradeable instruments and their specific trading windows.
All times are in GMT (will be automatically adjusted for GMT+1/BST).

Trading Windows per Instrument:
- USD/JPY: 7:00 AM – 9:00 AM (Tokyo-London transition/reversal)
- FTSE 100 / DAX: 8:00 AM, 9:30 AM – 11:00 AM (Morning correction)
- EUR/USD & GBP/USD: 10:00 AM – 11:30 AM (Post-London open settling)
- S&P 500 / NASDAQ: 2:30 PM - 3:30 PM – 4:30 PM (Afternoon fade)
- USD/JPY: 2:30 PM – 4:00 PM (Correction after NY volatility)
"""

from datetime import time
from typing import Dict, List, Any


# Instrument configuration dictionary
INSTRUMENTS = {
    # USD/JPY - Two trading windows
    'USDJPY': {
        'name': 'USD/JPY',
        'symbol': 'USDJPY',
        'enabled': True,
        # Recovery settings tailored for USDJPY volatility (~100-150 pip daily range)
        'recovery': {
            'grid_spacing_pips': 15,      # Grid every 15 pips (not too tight)
            'dca_trigger_pips': 35,       # DCA after 35 pips underwater
            'hedge_trigger_pips': 50,     # Hedge after 50 pips
            'dca_multiplier': 1.5,        # 1.5x scaling (less aggressive)
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        'windows': [
            {
                'name': 'Tokyo-London Transition',
                'start': time(7, 0),   # 7:00 AM GMT
                'end': time(9, 0),     # 9:00 AM GMT
                'strategy_type': 'reversal',
                'description': 'Tokyo-London transition/reversal strategy',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 7,
            },
            {
                'name': 'NY Correction',
                'start': time(14, 30),  # 2:30 PM GMT
                'end': time(16, 0),     # 4:00 PM GMT
                'strategy_type': 'correction',
                'description': 'Correction after initial NY volatility',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 7,
            }
        ]
    },

    # FTSE 100 (UK100)
    'UK100': {
        'name': 'FTSE 100',
        'symbol': 'UK100',
        'enabled': True,
        # Recovery settings for UK100 (~100-200 point daily range)
        'recovery': {
            'grid_spacing_pips': 35,      # Grid every 35 points
            'dca_trigger_pips': 70,       # DCA after 70 points
            'hedge_trigger_pips': 90,     # Hedge after 90 points
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        'windows': [
            {
                'name': 'Morning Correction',
                'start': time(9, 30),   # 9:30 AM GMT
                'end': time(11, 0),     # 11:00 AM GMT
                'strategy_type': 'correction',
                'description': 'The morning correction after market open',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 8,
            }
        ]
    },

    # DAX (Germany 30)
    'GER30': {
        'name': 'DAX',
        'symbol': 'GER30',
        'enabled': True,
        # Recovery settings for GER30 (~200-400 point daily range - VERY volatile)
        'recovery': {
            'grid_spacing_pips': 45,      # Grid every 45 points (wider for high volatility)
            'dca_trigger_pips': 90,       # DCA after 90 points
            'hedge_trigger_pips': 120,    # Hedge after 120 points
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        'windows': [
            {
                'name': 'Morning Correction',
                'start': time(9, 30),   # 9:30 AM GMT
                'end': time(11, 0),     # 11:00 AM GMT
                'strategy_type': 'correction',
                'description': 'The morning correction after market open',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 8,
            }
        ]
    },

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
        'windows': [
            {
                'name': 'Post-London Open',
                'start': time(10, 0),   # 10:00 AM GMT
                'end': time(11, 30),    # 11:30 AM GMT
                'strategy_type': 'settling',
                'description': 'Post-London open "settling" period',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 7,
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
        'windows': [
            {
                'name': 'Post-London Open',
                'start': time(10, 0),   # 10:00 AM GMT
                'end': time(11, 30),    # 11:30 AM GMT
                'strategy_type': 'settling',
                'description': 'Post-London open "settling" period',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 7,
            }
        ]
    },

    # S&P 500 (US500)
    'US500': {
        'name': 'S&P 500',
        'symbol': 'US500',
        'enabled': True,
        # Recovery settings for US500 (~50-100 point daily range)
        'recovery': {
            'grid_spacing_pips': 25,      # Grid every 25 points
            'dca_trigger_pips': 50,       # DCA after 50 points
            'hedge_trigger_pips': 70,     # Hedge after 70 points
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        'windows': [
            {
                'name': 'Afternoon Fade',
                'start': time(14, 30),  # 2:30 PM GMT
                'end': time(16, 30),    # 4:30 PM GMT
                'strategy_type': 'fade',
                'description': 'The afternoon "fade" strategy',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 8,
            }
        ]
    },

    # NASDAQ (NDAQ)
    'NDAQ': {
        'name': 'NASDAQ',
        'symbol': 'NDAQ',
        'enabled': True,
        # Recovery settings for NDAQ (~300-600 point daily range - EXTREMELY volatile!)
        'recovery': {
            'grid_spacing_pips': 60,      # Grid every 60 points (widest spacing for high volatility)
            'dca_trigger_pips': 120,      # DCA after 120 points
            'hedge_trigger_pips': 150,    # Hedge after 150 points
            'dca_multiplier': 1.5,
            'max_grid_levels': 4,
            'max_dca_levels': 3,
        },
        'windows': [
            {
                'name': 'Afternoon Fade',
                'start': time(14, 30),  # 2:30 PM GMT
                'end': time(16, 30),    # 4:30 PM GMT
                'strategy_type': 'fade',
                'description': 'The afternoon "fade" strategy',
                'close_all_at_end': True,          # Close ALL trades at window end
                'min_confluence_score': 8,
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
