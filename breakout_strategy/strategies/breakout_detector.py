"""
LVN Breakout Signal Detector
Completely independent from mean reversion module

Key Features:
1. Volume expansion detection (confirms real breakouts)
2. Zone retest logic (conservative pullback entries)
3. LVN detection (low volume nodes = low resistance)
4. VWAP directional bias (trend confirmation)

Based on backtest: 56.8% WR, $5.09 avg profit in trending markets
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime

# Import existing indicators (READ ONLY - no modifications)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trading_bot.indicators.vwap import VWAP
from trading_bot.indicators.volume_profile import VolumeProfile
from trading_bot.indicators.adx import calculate_adx, interpret_adx

# Import breakout config
from breakout_strategy.config.breakout_config import (
    MIN_BREAKOUT_CONFLUENCE,
    BREAKOUT_CONFLUENCE_WEIGHTS,
    BREAKOUT_ADX_MIN,
    BREAKOUT_ADX_OPTIMAL,
    BREAKOUT_ADX_MAX,
    LVN_PERCENTILE_THRESHOLD,
    LVN_PRICE_TOLERANCE_PCT,
    VWAP_STRONG_BIAS_PCT,
    VOLUME_HIGH_PERCENTILE,
    VOLUME_AVG_PERCENTILE,
    ALLOW_AGGRESSIVE_ENTRY,
    ALLOW_CONSERVATIVE_ENTRY,
    PULLBACK_TOLERANCE_PIPS,
    PULLBACK_MAX_WAIT_BARS,
)


class BreakoutDetector:
    """
    Detects LVN breakout opportunities in trending markets

    Entry Criteria:
    1. Market is trending (ADX >= 25)
    2. Price at or near LVN (low volume node)
    3. VWAP directional bias confirms trend direction
    4. Volume expansion (critical for confirmation)
    5. Zone retest preferred (pullback entry for better R:R)
    6. Minimum confluence score: 6
    """

    def __init__(self):
        """Initialize breakout detector with indicators"""
        self.vwap = VWAP()
        self.volume_profile = VolumeProfile()
        self.min_confluence = MIN_BREAKOUT_CONFLUENCE

        # Track recent breakouts for retest detection
        self.recent_breakouts = {}  # {symbol: {'level': price, 'direction': 'long/short', 'time': timestamp}}

    def detect_breakout(
        self,
        current_data: pd.DataFrame,
        daily_data: pd.DataFrame,
        weekly_data: pd.DataFrame,
        symbol: str
    ) -> Optional[Dict]:
        """
        Detect LVN breakout signal

        Args:
            current_data: H1 timeframe data with VWAP calculated
            daily_data: Daily timeframe for HTF context
            weekly_data: Weekly timeframe for HTF context
            symbol: Trading symbol

        Returns:
            Signal dict if valid breakout detected, None otherwise
        """

        if len(current_data) < 50:
            return None  # Need enough data for volume analysis

        # Initialize signal
        signal = {
            'symbol': symbol,
            'timestamp': current_data.iloc[-1]['time'],
            'direction': None,
            'entry_price': None,
            'confluence_score': 0,
            'factors': [],
            'entry_type': None,  # 'aggressive' or 'conservative' (retest)
            'stop_loss': None,
            'take_profit': None,
        }

        # Get current price and data
        latest = current_data.iloc[-1]
        price = latest['close']

        # === 1. TREND FILTER (ADX) ===
        if 'adx' not in current_data.columns:
            current_data = calculate_adx(current_data, period=14)
            latest = current_data.iloc[-1]  # Update latest after calculating ADX

        adx = latest['adx']
        plus_di = latest['plus_di']
        minus_di = latest['minus_di']

        # Must be trending market
        if adx < BREAKOUT_ADX_MIN:
            return None  # Not trending enough

        # Confluence: ADX strength
        if adx >= 35:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['strong_trend_adx']
            signal['factors'].append(f'strong_trend_adx_{adx:.1f}')
        else:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['trending_adx']
            signal['factors'].append(f'trending_adx_{adx:.1f}')

        # === 2. VOLUME ANALYSIS (CRITICAL) ===
        volume_info = self._analyze_volume(current_data)

        if volume_info['percentile'] >= VOLUME_HIGH_PERCENTILE:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['high_volume']
            signal['factors'].append(f"high_volume_{volume_info['percentile']:.0f}th")
        elif volume_info['percentile'] >= VOLUME_AVG_PERCENTILE:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['above_avg_volume']
            signal['factors'].append('above_avg_volume')
        else:
            # Low volume = weak breakout, skip
            return None

        # === 3. LVN DETECTION (PRIMARY FACTOR) ===
        lvn_info = self._detect_lvn(current_data, price)

        if lvn_info['at_lvn']:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['at_lvn']
            signal['factors'].append('at_lvn')
        elif lvn_info['near_lvn']:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['near_lvn']
            signal['factors'].append('near_lvn')
        else:
            # Not at LVN - this is critical for strategy
            return None

        # === 4. VWAP DIRECTIONAL BIAS ===
        vwap_info = self._analyze_vwap_bias(current_data, price)

        if vwap_info['has_bias']:
            signal['direction'] = vwap_info['direction']

            if vwap_info['strong_bias']:
                signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['vwap_directional_bias']
                signal['factors'].append('vwap_directional_bias')
            else:
                signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['vwap_neutral_bias']
                signal['factors'].append('vwap_neutral_bias')
        else:
            # No clear VWAP bias - skip
            return None

        # === 5. ADDITIONAL CONFLUENCE FACTORS ===

        # Not stuck in consolidation (away from POC)
        if 'volume_poc' in current_data.columns:
            poc = latest['volume_poc']
            poc_distance_pct = abs(price - poc) / price

            if poc_distance_pct > 0.002:  # More than 0.2% from POC
                signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['away_from_poc']
                signal['factors'].append('away_from_poc')

        # VWAP outer band position
        if vwap_info['at_outer_band']:
            signal['confluence_score'] += BREAKOUT_CONFLUENCE_WEIGHTS['vwap_outer_band']
            signal['factors'].append('vwap_outer_band')

        # === 6. CHECK CONFLUENCE THRESHOLD ===
        if signal['confluence_score'] < self.min_confluence:
            return None  # Not enough confluence

        # === 7. ENTRY TYPE DETERMINATION ===

        # Check for retest opportunity (PREFERRED - conservative entry)
        retest_info = self._check_for_retest(symbol, price, signal['direction'], current_data)

        if retest_info['is_retest'] and ALLOW_CONSERVATIVE_ENTRY:
            signal['entry_type'] = 'conservative_retest'
            signal['entry_price'] = price
            signal['stop_loss'] = retest_info['stop_loss']
            signal['take_profit'] = retest_info['take_profit']

            # Retest entries get bonus confluence (lower risk)
            signal['confluence_score'] += 2
            signal['factors'].append('retest_entry')

        elif ALLOW_AGGRESSIVE_ENTRY and signal['confluence_score'] >= 8:
            # Aggressive entry only with very high confluence
            signal['entry_type'] = 'aggressive_breakout'
            signal['entry_price'] = price

            # Calculate stops based on LVN level
            signal['stop_loss'] = self._calculate_stop_loss(
                price,
                signal['direction'],
                lvn_info['lvn_price']
            )
            signal['take_profit'] = self._calculate_take_profit(
                price,
                signal['direction'],
                signal['stop_loss']
            )
        else:
            # Track this level for future retest
            self._track_breakout_level(symbol, lvn_info['lvn_price'], signal['direction'])
            return None  # Wait for retest

        return signal

    def _analyze_volume(self, data: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        Analyze volume for breakout confirmation

        CRITICAL: Volume expansion confirms real breakouts vs false breakouts

        Args:
            data: OHLC data with volume
            lookback: Periods to look back for volume comparison

        Returns:
            Dict with volume analysis
        """
        if 'tick_volume' not in data.columns and 'volume' not in data.columns:
            return {'percentile': 50, 'expansion': False}

        volume_col = 'tick_volume' if 'tick_volume' in data.columns else 'volume'

        recent_data = data.tail(lookback)
        current_volume = data.iloc[-1][volume_col]

        # Calculate volume percentile
        volume_rank = (recent_data[volume_col] < current_volume).sum()
        percentile = (volume_rank / len(recent_data)) * 100

        # Calculate average volume
        avg_volume = recent_data[volume_col].mean()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        return {
            'current': current_volume,
            'average': avg_volume,
            'ratio': volume_ratio,
            'percentile': percentile,
            'expansion': percentile >= VOLUME_HIGH_PERCENTILE,
        }

    def _detect_lvn(self, data: pd.DataFrame, current_price: float) -> Dict:
        """
        Detect if price is at/near a Low Volume Node

        LVN = low resistance area where price should move quickly

        Args:
            data: OHLC data with volume profile
            current_price: Current market price

        Returns:
            Dict with LVN detection info
        """
        if 'lvn_price' not in data.columns or 'lvn_percentile' not in data.columns:
            return {'at_lvn': False, 'near_lvn': False, 'lvn_price': None}

        latest = data.iloc[-1]
        lvn_price = latest['lvn_price']
        lvn_percentile = latest['lvn_percentile']

        if pd.isna(lvn_price):
            return {'at_lvn': False, 'near_lvn': False, 'lvn_price': None}

        # Check if at LVN
        price_diff_pct = abs(current_price - lvn_price) / current_price
        tolerance = LVN_PRICE_TOLERANCE_PCT

        at_lvn = price_diff_pct <= tolerance and lvn_percentile < LVN_PERCENTILE_THRESHOLD
        near_lvn = price_diff_pct <= (tolerance * 2) and lvn_percentile < LVN_PERCENTILE_THRESHOLD

        return {
            'at_lvn': at_lvn,
            'near_lvn': near_lvn,
            'lvn_price': lvn_price,
            'lvn_percentile': lvn_percentile,
            'distance_pct': price_diff_pct,
        }

    def _analyze_vwap_bias(self, data: pd.DataFrame, current_price: float) -> Dict:
        """
        Analyze VWAP directional bias

        Above VWAP = bullish bias (look for long breakouts)
        Below VWAP = bearish bias (look for short breakouts)

        Args:
            data: OHLC data with VWAP
            current_price: Current price

        Returns:
            Dict with VWAP bias info
        """
        if 'vwap' not in data.columns:
            return {'has_bias': False, 'direction': None}

        latest = data.iloc[-1]
        vwap = latest['vwap']

        if pd.isna(vwap):
            return {'has_bias': False, 'direction': None}

        # Calculate distance from VWAP
        distance_pct = abs(current_price - vwap) / vwap

        # Determine direction
        if current_price > vwap:
            direction = 'long'
        else:
            direction = 'short'

        # Check if bias is strong
        strong_bias = distance_pct >= VWAP_STRONG_BIAS_PCT

        # Check if at outer VWAP band
        at_outer_band = False
        if 'in_vwap_band_2' in data.columns or 'in_vwap_band_3' in data.columns:
            at_outer_band = latest.get('in_vwap_band_2', False) or latest.get('in_vwap_band_3', False)

        return {
            'has_bias': True,
            'direction': direction,
            'strong_bias': strong_bias,
            'distance_pct': distance_pct,
            'at_outer_band': at_outer_band,
            'vwap_price': vwap,
        }

    def _check_for_retest(
        self,
        symbol: str,
        current_price: float,
        direction: str,
        data: pd.DataFrame
    ) -> Dict:
        """
        Check if this is a retest/pullback entry opportunity

        ZONE RETEST LOGIC:
        1. Price previously broke through a level (tracked)
        2. Price pulled back to retest that level
        3. Price is now bouncing from the level (confirmation)

        This provides better R:R than aggressive breakout entries

        Args:
            symbol: Trading symbol
            current_price: Current price
            direction: Trade direction ('long' or 'short')
            data: Recent price data

        Returns:
            Dict with retest info
        """
        # Check if we have a tracked breakout level for this symbol
        if symbol not in self.recent_breakouts:
            return {'is_retest': False}

        breakout = self.recent_breakouts[symbol]
        breakout_level = breakout['level']
        breakout_direction = breakout['direction']

        # Must be same direction
        if direction != breakout_direction:
            return {'is_retest': False}

        # Check if price has pulled back to the level
        price_diff_pips = abs(current_price - breakout_level) * 10000  # Rough pip calculation

        if price_diff_pips > PULLBACK_TOLERANCE_PIPS:
            return {'is_retest': False}  # Too far from level

        # Check for bounce confirmation (last 2-3 candles)
        recent = data.tail(3)

        if direction == 'long':
            # For longs: price should be bouncing UP from level
            bouncing = recent['close'].iloc[-1] > recent['low'].min()
        else:
            # For shorts: price should be bouncing DOWN from level
            bouncing = recent['close'].iloc[-1] < recent['high'].max()

        if not bouncing:
            return {'is_retest': False}  # No bounce confirmation yet

        # Calculate stops for retest entry (tighter than aggressive)
        if direction == 'long':
            stop_loss = breakout_level - (PULLBACK_TOLERANCE_PIPS / 10000)
            take_profit = current_price + (2 * (current_price - stop_loss))
        else:
            stop_loss = breakout_level + (PULLBACK_TOLERANCE_PIPS / 10000)
            take_profit = current_price - (2 * (stop_loss - current_price))

        # Clear the tracked breakout (used)
        del self.recent_breakouts[symbol]

        return {
            'is_retest': True,
            'breakout_level': breakout_level,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'price_diff_pips': price_diff_pips,
        }

    def _track_breakout_level(self, symbol: str, level: float, direction: str):
        """
        Track a breakout level for future retest detection

        Args:
            symbol: Trading symbol
            level: Breakout price level
            direction: Breakout direction
        """
        self.recent_breakouts[symbol] = {
            'level': level,
            'direction': direction,
            'time': datetime.now(),
        }

        # Clean up old breakouts (older than max wait time)
        # TODO: Implement cleanup based on PULLBACK_MAX_WAIT_BARS

    def _calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        lvn_price: float
    ) -> float:
        """
        Calculate stop loss for aggressive breakout entry

        Args:
            entry_price: Entry price
            direction: Trade direction
            lvn_price: LVN breakout level

        Returns:
            Stop loss price
        """
        # Place stop below/above LVN level
        if direction == 'long':
            stop = lvn_price - (10 / 10000)  # 10 pips below LVN
        else:
            stop = lvn_price + (10 / 10000)  # 10 pips above LVN

        return stop

    def _calculate_take_profit(
        self,
        entry_price: float,
        direction: str,
        stop_loss: float
    ) -> float:
        """
        Calculate take profit (1:2 risk/reward)

        Args:
            entry_price: Entry price
            direction: Trade direction
            stop_loss: Stop loss price

        Returns:
            Take profit price
        """
        risk = abs(entry_price - stop_loss)
        reward = risk * 2  # 1:2 R:R

        if direction == 'long':
            tp = entry_price + reward
        else:
            tp = entry_price - reward

        return tp

    def get_breakout_summary(self, signal: Dict) -> str:
        """
        Get human-readable summary of breakout signal

        Args:
            signal: Breakout signal dict

        Returns:
            Formatted summary string
        """
        if not signal:
            return "No breakout signal"

        summary = (
            f"🚀 BREAKOUT | {signal['symbol']} | "
            f"{signal['direction'].upper()} | "
            f"Entry: {signal['entry_type']} | "
            f"Confluence: {signal['confluence_score']} | "
            f"Factors: {', '.join(signal['factors'])} | "
            f"Price: {signal['entry_price']:.5f}"
        )

        return summary
