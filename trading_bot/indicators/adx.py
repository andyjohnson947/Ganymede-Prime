"""
Average Directional Index (ADX) - Trend Strength Indicator
Used to determine if market is trending or ranging
"""

import pandas as pd
import numpy as np


def calculate_adx(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate ADX (Average Directional Index)

    Args:
        data: DataFrame with 'high', 'low', 'close' columns
        period: Period for ADX calculation (default 14)

    Returns:
        DataFrame with ADX, +DI, -DI columns added
    """
    df = data.copy()

    # Calculate True Range
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
    df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

    # Calculate Directional Movement
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']

    # Positive and Negative Directional Movement
    df['plus_dm'] = np.where(
        (df['up_move'] > df['down_move']) & (df['up_move'] > 0),
        df['up_move'],
        0
    )
    df['minus_dm'] = np.where(
        (df['down_move'] > df['up_move']) & (df['down_move'] > 0),
        df['down_move'],
        0
    )

    # Smooth the values using Wilder's smoothing (exponential moving average)
    alpha = 1.0 / period

    df['atr'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()
    df['plus_di'] = 100 * (df['plus_dm'].ewm(alpha=alpha, adjust=False).mean() / df['atr'])
    df['minus_di'] = 100 * (df['minus_dm'].ewm(alpha=alpha, adjust=False).mean() / df['atr'])

    # Calculate DX (Directional Index)
    df['dx'] = 100 * np.abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])

    # Calculate ADX (smoothed DX)
    df['adx'] = df['dx'].ewm(alpha=alpha, adjust=False).mean()

    # Clean up intermediate columns
    df.drop(['high_low', 'high_close', 'low_close', 'tr', 'up_move', 'down_move',
             'plus_dm', 'minus_dm', 'dx'], axis=1, inplace=True)

    return df


def interpret_adx(adx_value: float, plus_di: float, minus_di: float) -> dict:
    """
    Interpret ADX reading and trend direction

    Args:
        adx_value: ADX value
        plus_di: +DI value
        minus_di: -DI value

    Returns:
        Dict with interpretation
    """
    # Determine trend strength
    if adx_value < 20:
        strength = "weak"
        market_type = "ranging"
    elif adx_value < 25:
        strength = "developing"
        market_type = "weak_trend"
    elif adx_value < 40:
        strength = "moderate"
        market_type = "trending"
    elif adx_value < 50:
        strength = "strong"
        market_type = "strong_trend"
    else:
        strength = "very_strong"
        market_type = "very_strong_trend"

    # Determine trend direction
    if plus_di > minus_di:
        direction = "bullish"
    else:
        direction = "bearish"

    # Confidence (higher when DI lines are far apart)
    confidence = abs(plus_di - minus_di)

    return {
        'adx': adx_value,
        'plus_di': plus_di,
        'minus_di': minus_di,
        'strength': strength,
        'market_type': market_type,
        'direction': direction,
        'confidence': confidence,
        'is_ranging': adx_value < 25,
        'is_trending': adx_value >= 25
    }


def analyze_candle_direction(data: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Analyze recent candle direction to confirm trend

    Args:
        data: DataFrame with OHLC data
        lookback: Number of candles to look back

    Returns:
        Dict with candle analysis
    """
    recent = data.tail(lookback)

    # Count bullish vs bearish candles
    bullish_candles = (recent['close'] > recent['open']).sum()
    bearish_candles = (recent['close'] < recent['open']).sum()

    # Calculate average body size
    body_sizes = np.abs(recent['close'] - recent['open'])
    avg_body = body_sizes.mean()

    # Calculate percentage of aligned candles
    total_candles = len(recent)
    bullish_pct = (bullish_candles / total_candles) * 100
    bearish_pct = (bearish_candles / total_candles) * 100

    # Determine if candles are aligned (mostly same direction)
    alignment_threshold = 70  # 70% of candles in same direction

    if bullish_pct >= alignment_threshold:
        alignment = "strong_bullish"
        aligned = True
        direction = "bullish"
    elif bearish_pct >= alignment_threshold:
        alignment = "strong_bearish"
        aligned = True
        direction = "bearish"
    elif bullish_pct >= 60:
        alignment = "weak_bullish"
        aligned = False
        direction = "bullish"
    elif bearish_pct >= 60:
        alignment = "weak_bearish"
        aligned = False
        direction = "bearish"
    else:
        alignment = "mixed"
        aligned = False
        direction = "neutral"

    return {
        'lookback': lookback,
        'bullish_candles': bullish_candles,
        'bearish_candles': bearish_candles,
        'bullish_pct': bullish_pct,
        'bearish_pct': bearish_pct,
        'alignment': alignment,
        'aligned': aligned,
        'direction': direction,
        'avg_body': avg_body
    }


def should_trade_based_on_trend(
    adx_value: float,
    plus_di: float,
    minus_di: float,
    candle_data: pd.DataFrame,
    candle_lookback: int = 5,
    adx_threshold: float = 25,
    allow_weak_trends: bool = True
) -> tuple[bool, str]:
    """
    Determine if we should trade based on trend analysis
    STRICT FILTER: Only allows mean reversion trades in ranging markets (ADX < 25)

    Args:
        adx_value: Current ADX value
        plus_di: Current +DI value
        minus_di: Current -DI value
        candle_data: Recent candle data
        candle_lookback: Number of candles to analyze
        adx_threshold: ADX threshold for "trending" market (default 25)
        allow_weak_trends: Deprecated - strict mode always blocks trends

    Returns:
        Tuple of (should_trade, reason)
    """
    # Get ADX interpretation
    adx_info = interpret_adx(adx_value, plus_di, minus_di)

    # STRICT RULE: Trending market (ADX >= 25) = NO TRADE
    # Mean reversion is unsafe in trending conditions regardless of candle patterns
    if adx_value >= adx_threshold:
        return False, f"Trending market (ADX: {adx_value:.1f}) - Mean reversion blocked (threshold: {adx_threshold})"

    # Ranging/Weak market (ADX < 25) = TRADE
    # These are ideal conditions for mean reversion
    if adx_value < adx_threshold:
        return True, f"Ranging market (ADX: {adx_value:.1f}) - Mean reversion safe"

    # Default: Block (safety fallback)
    return False, f"Trend filter - default block (ADX: {adx_value:.1f})"
