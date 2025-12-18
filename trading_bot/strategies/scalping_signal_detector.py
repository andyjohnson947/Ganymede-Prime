"""
Scalping Signal Detector
Fast momentum and breakout signals for M1/M5 timeframes
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime

from utils.logger import logger


class ScalpingSignalDetector:
    """Detect scalping signals based on momentum, volume, and price action"""

    def __init__(self,
                 momentum_period: int = 14,
                 volume_spike_threshold: float = 1.5,
                 breakout_lookback: int = 20):
        """
        Initialize scalping signal detector

        Args:
            momentum_period: Period for momentum calculation (RSI/Stochastic)
            volume_spike_threshold: Volume multiplier for spike detection
            breakout_lookback: Bars to look back for breakout levels
        """
        self.momentum_period = momentum_period
        self.volume_spike_threshold = volume_spike_threshold
        self.breakout_lookback = breakout_lookback

    def detect_signal(self, data: pd.DataFrame, symbol: str) -> Optional[Dict]:
        """
        Detect scalping signal based on momentum + volume + breakout

        Args:
            data: M1/M5 OHLCV data (minimum 50 bars recommended)
            symbol: Trading symbol

        Returns:
            Dict with signal info or None if no signal
        """
        if len(data) < 50:
            logger.warning(f"Insufficient data for scalping signal: {len(data)} bars")
            return None

        # Get current candle
        latest = data.iloc[-1]
        prev = data.iloc[-2]

        price = latest['close']

        # Initialize signal
        signal = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'price': price,
            'direction': None,
            'strength': 0,  # 0-100 signal strength
            'entry_reason': [],
            'should_trade': False,
            'stop_loss': None,
            'take_profit': None,
        }

        # 1. Calculate RSI for momentum
        rsi = self._calculate_rsi(data['close'], period=self.momentum_period)
        current_rsi = rsi.iloc[-1]

        # 2. Calculate Stochastic for entry timing
        stoch_k, stoch_d = self._calculate_stochastic(data, period=self.momentum_period)
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        prev_k = stoch_k.iloc[-2]
        prev_d = stoch_d.iloc[-2]

        # 3. Volume analysis
        volume_spike = self._detect_volume_spike(data)

        # 4. Price action (breakouts, rejections)
        breakout_signal = self._detect_breakout(data, self.breakout_lookback)

        # 5. Candle pattern
        bullish_candle = latest['close'] > latest['open']
        bearish_candle = latest['close'] < latest['open']
        strong_candle = abs(latest['close'] - latest['open']) > abs(prev['close'] - prev['open']) * 1.2

        # === BUY SIGNAL LOGIC ===
        buy_score = 0
        buy_reasons = []

        # RSI oversold bounce
        if 20 < current_rsi < 40:
            buy_score += 25
            buy_reasons.append(f"RSI oversold bounce ({current_rsi:.1f})")

        # Stochastic bullish cross in oversold
        if current_k > current_d and prev_k <= prev_d and current_k < 40:
            buy_score += 30
            buy_reasons.append(f"Stochastic bullish cross ({current_k:.1f})")

        # Volume spike + bullish candle
        if volume_spike and bullish_candle:
            buy_score += 25
            buy_reasons.append("Volume spike with bullish candle")

        # Breakout above resistance
        if breakout_signal == 'bullish_breakout':
            buy_score += 30
            buy_reasons.append("Bullish breakout")

        # Strong bullish momentum candle
        if bullish_candle and strong_candle:
            buy_score += 15
            buy_reasons.append("Strong bullish momentum candle")

        # === SELL SIGNAL LOGIC ===
        sell_score = 0
        sell_reasons = []

        # RSI overbought rejection
        if 60 < current_rsi < 80:
            sell_score += 25
            sell_reasons.append(f"RSI overbought rejection ({current_rsi:.1f})")

        # Stochastic bearish cross in overbought
        if current_k < current_d and prev_k >= prev_d and current_k > 60:
            sell_score += 30
            sell_reasons.append(f"Stochastic bearish cross ({current_k:.1f})")

        # Volume spike + bearish candle
        if volume_spike and bearish_candle:
            sell_score += 25
            sell_reasons.append("Volume spike with bearish candle")

        # Breakdown below support
        if breakout_signal == 'bearish_breakout':
            sell_score += 30
            sell_reasons.append("Bearish breakdown")

        # Strong bearish momentum candle
        if bearish_candle and strong_candle:
            sell_score += 15
            sell_reasons.append("Strong bearish momentum candle")

        # === DETERMINE SIGNAL ===
        # Require minimum 50 score for entry (multiple confirmations)
        min_score = 50

        if buy_score >= min_score and buy_score > sell_score:
            signal['direction'] = 'buy'
            signal['strength'] = min(buy_score, 100)
            signal['entry_reason'] = buy_reasons
            signal['should_trade'] = True

            # Calculate stop loss and take profit
            signal['stop_loss'] = self._calculate_buy_stop(data, latest)
            signal['take_profit'] = self._calculate_buy_target(latest, signal['stop_loss'])

        elif sell_score >= min_score and sell_score > buy_score:
            signal['direction'] = 'sell'
            signal['strength'] = min(sell_score, 100)
            signal['entry_reason'] = sell_reasons
            signal['should_trade'] = True

            # Calculate stop loss and take profit
            signal['stop_loss'] = self._calculate_sell_stop(data, latest)
            signal['take_profit'] = self._calculate_sell_target(latest, signal['stop_loss'])

        return signal if signal['should_trade'] else None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI (Relative Strength Index)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_stochastic(self, data: pd.DataFrame, period: int = 14) -> tuple:
        """Calculate Stochastic Oscillator (%K, %D)"""
        low_min = data['low'].rolling(window=period).min()
        high_max = data['high'].rolling(window=period).max()

        # %K line
        k = 100 * (data['close'] - low_min) / (high_max - low_min)

        # %D line (3-period SMA of %K)
        d = k.rolling(window=3).mean()

        return k, d

    def _detect_volume_spike(self, data: pd.DataFrame) -> bool:
        """Detect volume spike (current volume > threshold * average)"""
        if 'tick_volume' not in data.columns:
            return False

        avg_volume = data['tick_volume'].iloc[-20:-1].mean()
        current_volume = data['tick_volume'].iloc[-1]

        return current_volume > avg_volume * self.volume_spike_threshold

    def _detect_breakout(self, data: pd.DataFrame, lookback: int = 20) -> Optional[str]:
        """
        Detect breakout above resistance or below support

        Returns:
            'bullish_breakout', 'bearish_breakout', or None
        """
        latest = data.iloc[-1]
        recent = data.iloc[-lookback:-1]

        resistance = recent['high'].max()
        support = recent['low'].min()

        # Bullish breakout: Close above recent highs
        if latest['close'] > resistance:
            return 'bullish_breakout'

        # Bearish breakdown: Close below recent lows
        if latest['close'] < support:
            return 'bearish_breakout'

        return None

    def _calculate_buy_stop(self, data: pd.DataFrame, latest: pd.Series) -> float:
        """
        Calculate stop loss for BUY order
        Place below recent swing low or below current candle low
        """
        # Use recent swing low (last 10 bars)
        recent_low = data['low'].iloc[-10:].min()

        # Conservative: Use the lower of recent swing low or current candle low - buffer
        candle_low = latest['low']
        buffer_pips = 0.0003  # ~3 pips buffer

        stop_loss = min(recent_low, candle_low) - buffer_pips

        return stop_loss

    def _calculate_sell_stop(self, data: pd.DataFrame, latest: pd.Series) -> float:
        """
        Calculate stop loss for SELL order
        Place above recent swing high or above current candle high
        """
        # Use recent swing high (last 10 bars)
        recent_high = data['high'].iloc[-10:].max()

        # Conservative: Use the higher of recent swing high or current candle high + buffer
        candle_high = latest['high']
        buffer_pips = 0.0003  # ~3 pips buffer

        stop_loss = max(recent_high, candle_high) + buffer_pips

        return stop_loss

    def _calculate_buy_target(self, latest: pd.Series, stop_loss: float) -> float:
        """
        Calculate take profit for BUY order
        Use 1.5:1 or 2:1 risk-reward ratio
        """
        entry_price = latest['close']
        risk = entry_price - stop_loss

        # 2:1 reward-risk ratio
        reward = risk * 2.0

        take_profit = entry_price + reward

        return take_profit

    def _calculate_sell_target(self, latest: pd.Series, stop_loss: float) -> float:
        """
        Calculate take profit for SELL order
        Use 1.5:1 or 2:1 risk-reward ratio
        """
        entry_price = latest['close']
        risk = stop_loss - entry_price

        # 2:1 reward-risk ratio
        reward = risk * 2.0

        take_profit = entry_price - reward

        return take_profit

    def get_signal_summary(self, signal: Dict) -> str:
        """Get human-readable signal summary"""
        if not signal or not signal.get('should_trade'):
            return "No scalping signal"

        summary = []
        summary.append("=" * 60)
        summary.append("🎯 SCALPING SIGNAL DETECTED")
        summary.append("=" * 60)
        summary.append(f"Symbol: {signal['symbol']}")
        summary.append(f"Direction: {signal['direction'].upper()}")
        summary.append(f"Price: {signal['price']:.5f}")
        summary.append(f"Signal Strength: {signal['strength']}/100")
        summary.append(f"Time: {signal['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append("")
        summary.append("Entry Reasons:")
        for reason in signal['entry_reason']:
            summary.append(f"  ✓ {reason}")
        summary.append("")
        summary.append(f"Stop Loss: {signal['stop_loss']:.5f}")
        summary.append(f"Take Profit: {signal['take_profit']:.5f}")

        # Calculate risk-reward
        if signal['direction'] == 'buy':
            risk_pips = (signal['price'] - signal['stop_loss']) * 10000
            reward_pips = (signal['take_profit'] - signal['price']) * 10000
        else:
            risk_pips = (signal['stop_loss'] - signal['price']) * 10000
            reward_pips = (signal['price'] - signal['take_profit']) * 10000

        rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0

        summary.append(f"Risk: {risk_pips:.1f} pips")
        summary.append(f"Reward: {reward_pips:.1f} pips")
        summary.append(f"R:R Ratio: 1:{rr_ratio:.1f}")
        summary.append("=" * 60)

        return "\n".join(summary)
