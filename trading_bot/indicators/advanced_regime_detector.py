"""
Advanced Market Regime Detector - Priority 2 Implementation

Uses institutional-grade techniques:
1. Hurst Exponent - Statistical measure of mean reversion vs trending
2. VHF (Vertical Horizontal Filter) - Early trend detection
3. ADX (Average Directional Index) - Trend strength confirmation

These catch regime changes BEFORE they destroy your account.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime
from indicators.adx import calculate_adx


class AdvancedRegimeDetector:
    """
    Detect market regime changes using statistical methods

    Methods:
    - Hurst Exponent: H < 0.5 = mean reverting, H > 0.5 = trending
    - VHF: Catches trend formation early
    """

    def __init__(
        self,
        hurst_period: int = 100,
        vhf_period: int = 28,
        adx_period: int = 14,
        hurst_ranging_threshold: float = 0.45,
        hurst_trending_threshold: float = 0.65,  # Raised from 0.55 - only HEAVY trends
        vhf_ranging_threshold: float = 0.25,
        vhf_trending_threshold: float = 0.45,  # Raised from 0.40 - only HEAVY trends
        adx_ranging_threshold: float = 20,
        adx_trending_threshold: float = 30  # Raised from 25 - only HEAVY trends
    ):
        """
        Initialize detector

        Args:
            hurst_period: Lookback for Hurst calculation (50-100 recommended)
            vhf_period: Lookback for VHF (28 standard)
            adx_period: Period for ADX calculation (14 standard)
            hurst_ranging_threshold: H < this = ranging (0.45 default)
            hurst_trending_threshold: H > this = HEAVY trending (0.65 - more permissive)
            vhf_ranging_threshold: VHF < this = ranging (0.25 default)
            vhf_trending_threshold: VHF > this = HEAVY trending (0.45 - more permissive)
            adx_ranging_threshold: ADX < this = ranging (20 default)
            adx_trending_threshold: ADX > this = HEAVY trending (30 - more permissive)
        """
        self.hurst_period = hurst_period
        self.vhf_period = vhf_period
        self.adx_period = adx_period
        self.hurst_ranging = hurst_ranging_threshold
        self.hurst_trending = hurst_trending_threshold
        self.vhf_ranging = vhf_ranging_threshold
        self.vhf_trending = vhf_trending_threshold
        self.adx_ranging = adx_ranging_threshold
        self.adx_trending = adx_trending_threshold

    def detect_regime(self, price_data: pd.DataFrame) -> Dict:
        """
        Detect current market regime using Hurst + VHF + ADX

        Args:
            price_data: DataFrame with OHLC data

        Returns:
            Dict with regime info and confidence
        """
        if price_data is None or len(price_data) < self.hurst_period:
            return {
                'regime': 'unknown',
                'confidence': 0.0,
                'hurst': None,
                'vhf': None,
                'adx': None,
                'reason': 'Insufficient data'
            }

        # Calculate indicators
        hurst = self.calculate_hurst_exponent(price_data)
        vhf = self.calculate_vhf(price_data)
        vhf_trend = self.calculate_vhf_trend(price_data)

        # Calculate ADX
        adx = None
        try:
            data_with_adx = calculate_adx(price_data.copy(), period=self.adx_period)
            if 'adx' in data_with_adx.columns:
                adx = data_with_adx['adx'].iloc[-1]
        except Exception:
            pass  # ADX calculation failed, will be None

        # Determine regime with confluence logic (all 3 indicators)
        regime, confidence, reason = self._classify_regime(hurst, vhf, vhf_trend, adx)

        return {
            'regime': regime,
            'confidence': confidence,
            'hurst': hurst,
            'vhf': vhf,
            'adx': adx,
            'vhf_trend': vhf_trend,
            'reason': reason,
            'timestamp': datetime.now()
        }

    def calculate_hurst_exponent(self, price_data: pd.DataFrame) -> Optional[float]:
        """
        Calculate Hurst Exponent using Rescaled Range (R/S) analysis

        H < 0.5: Mean reverting (anti-persistent) - SAFE for recovery
        H = 0.5: Random walk (no memory)
        H > 0.5: Trending (persistent) - DANGEROUS for recovery

        Args:
            price_data: DataFrame with close prices

        Returns:
            Hurst exponent (0-1) or None if calculation fails
        """
        try:
            # Use log returns for better statistical properties
            closes = price_data['close'].values[-self.hurst_period:]

            if len(closes) < 50:
                return None

            log_returns = np.log(closes[1:] / closes[:-1])

            # Remove any NaN or inf values
            log_returns = log_returns[np.isfinite(log_returns)]

            if len(log_returns) < 20:
                return None

            # Calculate R/S for different lag values
            lags = range(2, min(len(log_returns) // 2, 50))
            rs_values = []

            for lag in lags:
                # Calculate mean
                mean = np.mean(log_returns[:lag])

                # Calculate cumulative deviation from mean
                deviations = log_returns[:lag] - mean
                cumsum = np.cumsum(deviations)

                # Calculate range (R)
                R = np.max(cumsum) - np.min(cumsum)

                # Calculate standard deviation (S)
                S = np.std(log_returns[:lag], ddof=1)

                # Avoid division by zero
                if S > 0:
                    rs_values.append(R / S)

            if len(rs_values) < 5:
                return None

            # Hurst exponent is the slope of log(R/S) vs log(lag)
            log_lags = np.log(list(lags[:len(rs_values)]))
            log_rs = np.log(rs_values)

            # Remove any NaN or inf
            valid_indices = np.isfinite(log_lags) & np.isfinite(log_rs)
            log_lags = log_lags[valid_indices]
            log_rs = log_rs[valid_indices]

            if len(log_lags) < 5:
                return None

            # Linear regression to get slope (Hurst exponent)
            hurst = np.polyfit(log_lags, log_rs, 1)[0]

            # Clamp to valid range [0, 1]
            hurst = max(0.0, min(1.0, hurst))

            return float(hurst)

        except Exception as e:
            print(f"⚠️  Hurst calculation error: {e}")
            return None

    def calculate_vhf(self, price_data: pd.DataFrame) -> Optional[float]:
        """
        Calculate Vertical Horizontal Filter (VHF)

        Measures trend vs chop:
        - Low VHF (< 0.25): Choppy, ranging market
        - High VHF (> 0.40): Strong trend
        - Rising VHF: Trend FORMING (early warning!)

        Formula: |Highest - Lowest| / Sum(|Close - Previous_Close|)

        Args:
            price_data: DataFrame with close prices

        Returns:
            VHF value or None if calculation fails
        """
        try:
            closes = price_data['close'].values[-self.vhf_period:]

            if len(closes) < self.vhf_period:
                return None

            # Numerator: absolute price range over period
            highest = np.max(closes)
            lowest = np.min(closes)
            numerator = abs(highest - lowest)

            # Denominator: sum of absolute bar-to-bar changes
            price_changes = np.abs(np.diff(closes))
            denominator = np.sum(price_changes)

            # Avoid division by zero
            if denominator == 0:
                return 0.0

            vhf = numerator / denominator

            return float(vhf)

        except Exception as e:
            print(f"⚠️  VHF calculation error: {e}")
            return None

    def calculate_vhf_trend(self, price_data: pd.DataFrame) -> Optional[str]:
        """
        Calculate if VHF is rising (trend forming) or falling (trend ending)

        This is THE early warning signal for regime change

        Returns:
            'rising', 'falling', 'stable', or None
        """
        try:
            # Calculate VHF for last 3 periods to detect trend
            if len(price_data) < self.vhf_period * 3:
                return None

            vhf_values = []
            for i in range(3):
                offset = self.vhf_period * i
                window = price_data.iloc[-(self.vhf_period * (i+1)):-offset] if offset > 0 else price_data.iloc[-(self.vhf_period * (i+1)):]
                vhf = self.calculate_vhf(window)
                if vhf is not None:
                    vhf_values.append(vhf)

            if len(vhf_values) < 3:
                return None

            # Reverse so oldest is first
            vhf_values = vhf_values[::-1]

            # Check trend
            if vhf_values[2] > vhf_values[1] > vhf_values[0]:
                return 'rising'
            elif vhf_values[2] < vhf_values[1] < vhf_values[0]:
                return 'falling'
            else:
                return 'stable'

        except Exception as e:
            print(f"⚠️  VHF trend calculation error: {e}")
            return None

    def _classify_regime(
        self,
        hurst: Optional[float],
        vhf: Optional[float],
        vhf_trend: Optional[str],
        adx: Optional[float]
    ) -> Tuple[str, float, str]:
        """
        Classify regime using confluence of Hurst + VHF + ADX

        PHILOSOPHY: Only block trading in HEAVY trending markets (2+ indicators strongly agree)
        Allow trading in slight trends / choppy markets (mean reversion can still work)

        Returns:
            (regime, confidence, reason)
        """
        # Handle missing data
        if hurst is None and vhf is None and adx is None:
            return 'unknown', 0.0, 'Insufficient data for calculation'

        # Count indicators voting for each regime
        trending_votes = 0
        ranging_votes = 0
        details = []

        # Hurst voting
        if hurst is not None:
            if hurst > self.hurst_trending:
                trending_votes += 1
                details.append(f"H:{hurst:.3f}↑")
            elif hurst < self.hurst_ranging:
                ranging_votes += 1
                details.append(f"H:{hurst:.3f}↓")
            else:
                details.append(f"H:{hurst:.3f}~")

        # VHF voting
        if vhf is not None:
            if vhf > self.vhf_trending:
                trending_votes += 1
                details.append(f"VHF:{vhf:.3f}↑")
            elif vhf < self.vhf_ranging:
                ranging_votes += 1
                details.append(f"VHF:{vhf:.3f}↓")
            else:
                details.append(f"VHF:{vhf:.3f}~")

        # ADX voting
        if adx is not None:
            if adx > self.adx_trending:
                trending_votes += 1
                details.append(f"ADX:{adx:.1f}↑")
            elif adx < self.adx_ranging:
                ranging_votes += 1
                details.append(f"ADX:{adx:.1f}↓")
            else:
                details.append(f"ADX:{adx:.1f}~")

        details_str = ", ".join(details)

        # CRITICAL ALERT: VHF rising rapidly = trend forming RIGHT NOW
        if vhf_trend == 'rising' and vhf is not None and vhf > self.vhf_ranging:
            return 'trending', 0.85, f'VHF RISING - trend forming | {details_str}'

        # HEAVY TRENDING: 2+ indicators strongly agree
        if trending_votes >= 2:
            confidence = 0.75 + (trending_votes - 2) * 0.10  # 75%, 85%, 95% for 2/3/3 votes
            return 'trending', confidence, f'HEAVY trend ({trending_votes}/3 agree) | {details_str}'

        # STRONG RANGING: 2+ indicators strongly agree
        if ranging_votes >= 2:
            confidence = 0.75 + (ranging_votes - 2) * 0.10
            return 'ranging', confidence, f'Strong ranging ({ranging_votes}/3 agree) | {details_str}'

        # SLIGHT TREND: Only 1 indicator shows trending (allow mean reversion)
        if trending_votes == 1:
            return 'choppy', 0.60, f'Slight trend (1/3) - tradeable | {details_str}'

        # SLIGHT RANGING: Only 1 indicator shows ranging
        if ranging_votes == 1:
            return 'choppy', 0.60, f'Choppy ranging (1/3) - tradeable | {details_str}'

        # TRANSITIONAL: No strong signals
        return 'choppy', 0.50, f'Transitional - tradeable | {details_str}'

    def is_safe_for_recovery(self, price_data: pd.DataFrame, min_confidence: float = 0.65) -> Tuple[bool, str]:
        """
        Determine if market is safe for recovery trading (Grid/Hedge/DCA)

        Args:
            price_data: OHLC data
            min_confidence: Minimum confidence required (0-1)

        Returns:
            (is_safe, reason)
        """
        regime_info = self.detect_regime(price_data)

        regime = regime_info['regime']
        confidence = regime_info['confidence']

        # CRITICAL: If VHF rising, NOT SAFE regardless of current regime
        if regime_info.get('vhf_trend') == 'rising':
            return False, f"❌ VHF RISING - trend forming (VHF: {regime_info['vhf']:.3f})"

        # Safe if ranging with good confidence
        if regime == 'ranging' and confidence >= min_confidence:
            return True, f"✅ RANGING confirmed (H: {regime_info['hurst']:.3f}, VHF: {regime_info['vhf']:.3f}, conf: {confidence:.0%})"

        # Safe if choppy with decent confidence (allow some uncertainty)
        if regime == 'choppy' and confidence >= 0.50:
            return True, f"✅ CHOPPY market (H: {regime_info['hurst']:.3f}, VHF: {regime_info['vhf']:.3f}, conf: {confidence:.0%})"

        # NOT SAFE if trending
        if regime == 'trending':
            return False, f"❌ TRENDING (H: {regime_info['hurst']:.3f}, VHF: {regime_info['vhf']:.3f}, conf: {confidence:.0%})"

        # Unknown or low confidence - err on side of caution
        return False, f"⚠️  Uncertain regime ({regime}, conf: {confidence:.0%})"

    def is_safe_for_mean_reversion(self, price_data: pd.DataFrame) -> Tuple[bool, str]:
        """
        Determine if market is safe for mean reversion NEW ENTRY trades

        MORE PERMISSIVE than recovery check - only blocks HEAVY trending markets
        (2+ indicators strongly agree on trending)

        Philosophy: Mean reversion can work in:
        - Ranging markets (best)
        - Choppy markets (good)
        - Slight trends (acceptable - might catch reversals)

        Only block in:
        - HEAVY trends (2+ indicators agree, confidence >= 75%)

        Args:
            price_data: OHLC data

        Returns:
            (is_safe, reason)
        """
        regime_info = self.detect_regime(price_data)

        regime = regime_info['regime']
        confidence = regime_info['confidence']
        hurst = regime_info.get('hurst', 0)
        vhf = regime_info.get('vhf', 0)
        adx = regime_info.get('adx', 0)

        # CRITICAL: If VHF rising RAPIDLY above trending threshold, block
        if regime_info.get('vhf_trend') == 'rising' and vhf and vhf > self.vhf_trending:
            return False, f"❌ VHF RISING above {self.vhf_trending:.2f} - strong trend forming | VHF: {vhf:.3f}"

        # Block only HEAVY trending (2+ indicators agree, confidence >= 75%)
        if regime == 'trending' and confidence >= 0.75:
            return False, f"❌ HEAVY TRENDING (conf: {confidence:.0%}) | H:{hurst:.3f}, VHF:{vhf:.3f}, ADX:{adx:.1f if adx else 'N/A'}"

        # Allow everything else (ranging, choppy, slight trends)
        if regime == 'ranging':
            return True, f"✅ RANGING - excellent for mean reversion | H:{hurst:.3f}, VHF:{vhf:.3f}, ADX:{adx:.1f if adx else 'N/A'}"

        if regime == 'choppy':
            return True, f"✅ CHOPPY - acceptable for mean reversion | H:{hurst:.3f}, VHF:{vhf:.3f}, ADX:{adx:.1f if adx else 'N/A'}"

        # Even slight trending (1 indicator only) is allowed
        if regime == 'trending' and confidence < 0.75:
            return True, f"✅ SLIGHT trend (conf: {confidence:.0%}) - tradeable | H:{hurst:.3f}, VHF:{vhf:.3f}, ADX:{adx:.1f if adx else 'N/A'}"

        # Unknown - allow (don't miss opportunities)
        return True, f"⚠️  Uncertain regime ({regime}) - allowing trade"

    def get_regime_strength(self, price_data: pd.DataFrame) -> Dict:
        """
        Get detailed regime strength metrics

        Returns:
            Dict with strength indicators
        """
        regime_info = self.detect_regime(price_data)

        hurst = regime_info.get('hurst')
        vhf = regime_info.get('vhf')

        if hurst is None or vhf is None:
            return {
                'mean_reversion_strength': 0.0,
                'trend_strength': 0.0,
                'uncertainty': 1.0
            }

        # Mean reversion strength (0-1): stronger when H is low
        # H=0.3 → strength=1.0, H=0.5 → strength=0.0
        mean_reversion_strength = max(0.0, min(1.0, (0.5 - hurst) * 5))

        # Trend strength (0-1): stronger when H is high
        # H=0.7 → strength=1.0, H=0.5 → strength=0.0
        trend_strength = max(0.0, min(1.0, (hurst - 0.5) * 5))

        # Uncertainty: low when regime is clear, high when in middle
        # H=0.5, VHF=0.3 → high uncertainty
        uncertainty = 1.0 - regime_info['confidence']

        return {
            'mean_reversion_strength': mean_reversion_strength,
            'trend_strength': trend_strength,
            'uncertainty': uncertainty,
            'vhf_rising': regime_info.get('vhf_trend') == 'rising'
        }
