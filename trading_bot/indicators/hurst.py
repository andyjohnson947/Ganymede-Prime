"""
Hurst Exponent - Measure trend persistence vs mean reversion
Used to determine if market is trending (H > 0.5) or mean-reverting (H < 0.5)
"""

import numpy as np
import pandas as pd
from typing import Tuple


def calculate_hurst_exponent(prices: pd.Series, max_lag: int = 100) -> float:
    """
    Calculate Hurst exponent using R/S (Rescaled Range) analysis

    Args:
        prices: Price series (close prices)
        max_lag: Maximum lag to use (default 100)

    Returns:
        float: Hurst exponent
            H < 0.5 = Mean-reverting (anti-persistent)
            H = 0.5 = Random walk (geometric Brownian motion)
            H > 0.5 = Trending (persistent)
    """
    if len(prices) < max_lag:
        max_lag = len(prices) // 2

    if max_lag < 10:
        return 0.5  # Not enough data, assume random walk

    # Calculate log returns
    log_returns = np.log(prices / prices.shift(1)).dropna()

    if len(log_returns) < 10:
        return 0.5

    lags = range(2, max_lag)
    tau = []

    for lag in lags:
        # Split the series into lag subseries
        subseries = [log_returns[i:i+lag].values for i in range(0, len(log_returns), lag)]

        # Filter out incomplete subseries
        subseries = [s for s in subseries if len(s) == lag]

        if len(subseries) == 0:
            continue

        # Calculate R/S for each subseries
        rs_values = []
        for series in subseries:
            mean = np.mean(series)
            # Mean-adjusted series
            Y = np.cumsum(series - mean)
            # Range
            R = np.max(Y) - np.min(Y)
            # Standard deviation
            S = np.std(series, ddof=1)

            if S > 0:
                rs_values.append(R / S)

        if len(rs_values) > 0:
            tau.append(np.mean(rs_values))

    if len(tau) < 2:
        return 0.5

    # Fit log-log plot to get Hurst exponent
    # log(R/S) = H * log(n) + c
    lags_array = np.array(list(lags[:len(tau)]))
    tau_array = np.array(tau)

    # Remove any invalid values
    valid_idx = (tau_array > 0) & np.isfinite(tau_array)
    if np.sum(valid_idx) < 2:
        return 0.5

    lags_array = lags_array[valid_idx]
    tau_array = tau_array[valid_idx]

    # Linear regression on log-log scale
    log_lags = np.log(lags_array)
    log_tau = np.log(tau_array)

    # y = mx + b, where m is the Hurst exponent
    coeffs = np.polyfit(log_lags, log_tau, 1)
    hurst = coeffs[0]

    # Clamp to valid range [0, 1]
    hurst = max(0.0, min(1.0, hurst))

    return hurst


def interpret_hurst(hurst: float) -> dict:
    """
    Interpret Hurst exponent value

    Args:
        hurst: Hurst exponent value

    Returns:
        Dict with interpretation
    """
    if hurst < 0.4:
        behavior = "strongly_mean_reverting"
        market_type = "ranging"
        recommendation = "Use mean reversion strategies"
    elif hurst < 0.5:
        behavior = "mean_reverting"
        market_type = "ranging"
        recommendation = "Mean reversion strategies favorable"
    elif hurst == 0.5:
        behavior = "random_walk"
        market_type = "random"
        recommendation = "No clear edge, use caution"
    elif hurst < 0.6:
        behavior = "weak_trend"
        market_type = "weak_trending"
        recommendation = "Trend following with caution"
    elif hurst < 0.7:
        behavior = "trending"
        market_type = "trending"
        recommendation = "Trend following strategies"
    else:
        behavior = "strongly_trending"
        market_type = "strong_trending"
        recommendation = "Strong trend following, avoid mean reversion"

    return {
        'hurst': hurst,
        'behavior': behavior,
        'market_type': market_type,
        'recommendation': recommendation,
        'is_mean_reverting': hurst < 0.5,
        'is_trending': hurst > 0.5,
        'is_random': abs(hurst - 0.5) < 0.05
    }


def combine_hurst_adx_analysis(
    hurst: float,
    adx: float,
    plus_di: float,
    minus_di: float
) -> dict:
    """
    Combine Hurst exponent with ADX for comprehensive market analysis

    Args:
        hurst: Hurst exponent
        adx: ADX value
        plus_di: +DI value
        minus_di: -DI value

    Returns:
        Dict with combined analysis and trading recommendation
    """
    hurst_info = interpret_hurst(hurst)

    # Determine market regime
    if hurst < 0.5 and adx < 25:
        regime = "ranging_confirmed"
        strategy = "mean_reversion"
        confidence = "very_high"
    elif hurst < 0.5 and adx >= 25:
        regime = "conflicting_signals"
        strategy = "caution"
        confidence = "low"
    elif hurst > 0.5 and adx >= 25:
        regime = "trending_confirmed"
        strategy = "trend_following"
        confidence = "very_high"
    elif hurst > 0.5 and adx < 25:
        regime = "early_trend"
        strategy = "trend_following"
        confidence = "medium"
    else:
        regime = "random"
        strategy = "avoid"
        confidence = "very_low"

    # Determine trend direction if trending
    direction = "bullish" if plus_di > minus_di else "bearish"

    return {
        'regime': regime,
        'strategy': strategy,
        'confidence': confidence,
        'direction': direction,
        'hurst': hurst,
        'adx': adx,
        'hurst_behavior': hurst_info['behavior'],
        'should_mean_revert': regime in ['ranging_confirmed', 'early_trend'] and hurst < 0.5,
        'should_trend_follow': regime in ['trending_confirmed', 'early_trend'] and hurst > 0.5,
        'danger_zone': regime == 'conflicting_signals'  # Mean reverting Hurst but trending ADX
    }
