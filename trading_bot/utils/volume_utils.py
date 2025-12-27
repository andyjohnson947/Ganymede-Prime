"""
Volume Utility Functions
Consolidates volume column handling across indicators
"""

import pandas as pd
from typing import Union


def get_volume_from_dataframe(df: pd.DataFrame, default_value: float = 1.0) -> pd.Series:
    """
    Extract volume column from DataFrame, handling both 'volume' and 'tick_volume'.

    MT5 data uses 'tick_volume' instead of 'volume'. This function provides
    a consistent interface across all indicators.

    Args:
        df: DataFrame with OHLCV data
        default_value: Default value to use if no volume column exists

    Returns:
        pd.Series: Volume data

    Example:
        >>> volume = get_volume_from_dataframe(h1_data)
        >>> vwap = (price * volume).cumsum() / volume.cumsum()
    """
    if 'volume' in df.columns:
        return df['volume']
    elif 'tick_volume' in df.columns:
        return df['tick_volume']
    else:
        # Fallback: equal-weighted if no volume data
        return pd.Series([default_value] * len(df), index=df.index)


def get_volume_from_row(row: Union[pd.Series, dict], default_value: float = 1.0) -> float:
    """
    Extract volume from a single row (Series or dict).

    Args:
        row: Row data as pd.Series or dict
        default_value: Default value if no volume found

    Returns:
        float: Volume value

    Example:
        >>> for _, row in df.iterrows():
        ...     volume = get_volume_from_row(row)
    """
    if 'volume' in row:
        return float(row['volume'])
    elif 'tick_volume' in row:
        return float(row['tick_volume'])
    else:
        return default_value


def ensure_volume_column(df: pd.DataFrame, default_value: float = 1.0) -> pd.DataFrame:
    """
    Ensure DataFrame has a 'volume' column, adding it if missing.

    Modifies DataFrame in-place if 'volume' doesn't exist.

    Args:
        df: DataFrame to check/modify
        default_value: Default value if no volume data

    Returns:
        pd.DataFrame: DataFrame with guaranteed 'volume' column

    Example:
        >>> df = ensure_volume_column(df)
        >>> assert 'volume' in df.columns
    """
    if 'volume' not in df.columns:
        if 'tick_volume' in df.columns:
            df['volume'] = df['tick_volume']
        else:
            df['volume'] = default_value

    return df
