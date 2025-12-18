"""
Average True Range (ATR) - Volatility Indicator
Used for dynamic stop loss placement in breakout trades
"""

import pandas as pd
import numpy as np


def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate ATR (Average True Range)

    Args:
        data: DataFrame with 'high', 'low', 'close' columns
        period: Period for ATR calculation (default 14)

    Returns:
        DataFrame with 'atr' column added
    """
    df = data.copy()

    # Calculate True Range
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
    df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

    # Smooth using Wilder's smoothing (exponential moving average)
    alpha = 1.0 / period
    df['atr'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()

    # Clean up intermediate columns
    df.drop(['high_low', 'high_close', 'low_close', 'tr'], axis=1, inplace=True)

    return df


def get_atr_value(data: pd.DataFrame, period: int = 14) -> float:
    """
    Get the latest ATR value

    Args:
        data: DataFrame with OHLC data
        period: ATR period

    Returns:
        Latest ATR value
    """
    if 'atr' not in data.columns:
        data = calculate_atr(data, period)

    return data.iloc[-1]['atr']


def calculate_atr_stop_loss(
    entry_price: float,
    atr_value: float,
    direction: str,
    atr_multiplier: float = 1.5
) -> float:
    """
    Calculate stop loss based on ATR

    Args:
        entry_price: Entry price of the trade
        atr_value: Current ATR value
        direction: Trade direction ('buy' or 'sell')
        atr_multiplier: ATR multiplier for stop distance (default 1.5)

    Returns:
        Stop loss price
    """
    stop_distance = atr_value * atr_multiplier

    if direction == 'buy':
        # For buy trades, stop below entry
        stop_loss = entry_price - stop_distance
    else:
        # For sell trades, stop above entry
        stop_loss = entry_price + stop_distance

    return stop_loss


def calculate_atr_take_profit(
    entry_price: float,
    stop_loss: float,
    direction: str,
    risk_reward_ratio: float = 2.0
) -> float:
    """
    Calculate take profit based on risk/reward ratio

    Args:
        entry_price: Entry price of the trade
        stop_loss: Stop loss price
        direction: Trade direction ('buy' or 'sell')
        risk_reward_ratio: Reward:Risk ratio (default 2.0 for 2R)

    Returns:
        Take profit price
    """
    # Calculate risk (distance from entry to stop)
    risk = abs(entry_price - stop_loss)

    # Calculate reward (risk * ratio)
    reward = risk * risk_reward_ratio

    if direction == 'buy':
        # For buy trades, TP above entry
        take_profit = entry_price + reward
    else:
        # For sell trades, TP below entry
        take_profit = entry_price - reward

    return take_profit


def get_breakout_risk_levels(
    data: pd.DataFrame,
    entry_price: float,
    direction: str,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
    risk_reward_ratio: float = 2.0
) -> dict:
    """
    Calculate complete risk management levels for breakout trade

    Args:
        data: DataFrame with OHLC data
        entry_price: Entry price
        direction: Trade direction ('buy' or 'sell')
        atr_period: ATR calculation period
        atr_multiplier: ATR multiplier for stop distance
        risk_reward_ratio: Reward:Risk ratio

    Returns:
        Dict with stop_loss, take_profit, atr_value, risk_pips, reward_pips
    """
    # Calculate ATR if not present
    if 'atr' not in data.columns:
        data = calculate_atr(data, atr_period)

    atr_value = data.iloc[-1]['atr']

    # Calculate stop loss
    stop_loss = calculate_atr_stop_loss(entry_price, atr_value, direction, atr_multiplier)

    # Calculate take profit
    take_profit = calculate_atr_take_profit(entry_price, stop_loss, direction, risk_reward_ratio)

    # Calculate pip distances (assuming 4-decimal forex pair)
    risk_pips = abs(entry_price - stop_loss) * 10000
    reward_pips = abs(take_profit - entry_price) * 10000

    return {
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'atr_value': atr_value,
        'atr_multiplier': atr_multiplier,
        'risk_reward_ratio': risk_reward_ratio,
        'risk_pips': risk_pips,
        'reward_pips': reward_pips
    }
