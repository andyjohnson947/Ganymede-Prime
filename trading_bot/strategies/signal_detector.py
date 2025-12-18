"""
Signal Detection with Confluence Scoring
Minimum confluence score: 4 (83.3% win rate at optimal score)
"""

import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime

from indicators.vwap import VWAP
from indicators.volume_profile import VolumeProfile
from indicators.htf_levels import HTFLevels
from indicators.adx import calculate_adx, should_trade_based_on_trend
from utils.logger import logger
from config.strategy_config import (
    MIN_CONFLUENCE_SCORE,
    CONFLUENCE_WEIGHTS,
    LEVEL_TOLERANCE_PCT,
    TREND_FILTER_ENABLED,
    ADX_PERIOD,
    ADX_THRESHOLD,
    CANDLE_LOOKBACK,
    ALLOW_WEAK_TRENDS
)


class SignalDetector:
    """Detect entry signals based on confluence of multiple factors"""

    def __init__(self):
        """Initialize signal detector with indicators"""
        self.vwap = VWAP()
        self.volume_profile = VolumeProfile()
        self.htf_levels = HTFLevels()

    def detect_signal(
        self,
        current_data: pd.DataFrame,
        daily_data: pd.DataFrame,
        weekly_data: pd.DataFrame,
        symbol: str
    ) -> Optional[Dict]:
        """
        Detect trading signal based on confluence

        Args:
            current_data: H1 timeframe data with VWAP calculated
            daily_data: D1 timeframe data
            weekly_data: W1 timeframe data
            symbol: Trading symbol

        Returns:
            Dict with signal info or None if no signal
        """
        if len(current_data) < 200:
            return None

        # Get current price
        latest = current_data.iloc[-1]
        price = latest['close']

        # Initialize signal
        signal = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'price': price,
            'direction': None,
            'confluence_score': 0,
            'factors': [],
            'should_trade': False,
            'vwap_signals': {},
            'vp_signals': {},
            'htf_signals': {}
        }

        # Calculate indicators if not already done
        if 'vwap' not in current_data.columns:
            current_data = self.vwap.calculate(current_data)

        # 1. Check VWAP signals
        vwap_signals = self.vwap.get_signals(current_data)
        signal['vwap_signals'] = vwap_signals

        # Check VWAP bands
        if vwap_signals['in_band_1']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('vwap_band_1', 1)
            signal['factors'].append('VWAP Band 1')
            signal['direction'] = 'buy' if vwap_signals['direction'] == 'below' else 'sell'

        elif vwap_signals['in_band_2']:
            # BREAKOUT FILTER: Check if this is a breakout (not mean reversion)
            breakout_info = self.detect_breakout_momentum(current_data, vwap_signals)

            if breakout_info['is_breakout']:
                # Price breaking out with momentum - block mean reversion trade
                signal['should_trade'] = False
                signal['reject_reason'] = (
                    f"Breakout momentum detected - {breakout_info['momentum']} "
                    f"({breakout_info['confidence']}/5 candles moving away from VWAP)"
                )
                logger.info(
                    f"⏸️  Signal BLOCKED by breakout filter | {symbol} | "
                    f"VWAP Band 2 | Momentum: {breakout_info['momentum']} | "
                    f"Confidence: {breakout_info['confidence']}/5 candles | "
                    f"Price: {price:.5f}"
                )
                return None  # Block the trade

            # No breakout detected - proceed with mean reversion
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('vwap_band_2', 1)
            signal['factors'].append('VWAP Band 2')
            signal['direction'] = 'buy' if vwap_signals['direction'] == 'below' else 'sell'

        # 2. Check Volume Profile signals
        vp_signals = self.volume_profile.get_signals(current_data, price, lookback=200)
        signal['vp_signals'] = vp_signals

        if vp_signals['at_poc']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('poc', 1)
            signal['factors'].append('POC')

        if vp_signals['above_vah']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('above_vah', 1)
            signal['factors'].append('Above VAH')

        if vp_signals['below_val']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('below_val', 1)
            signal['factors'].append('Below VAL')

        if vp_signals['at_lvn']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('lvn', 1)
            signal['factors'].append('Low Volume Node')

        if vp_signals['at_swing_high']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('swing_high', 1)
            signal['factors'].append('Swing High')

        if vp_signals['at_swing_low']:
            signal['confluence_score'] += CONFLUENCE_WEIGHTS.get('swing_low', 1)
            signal['factors'].append('Swing Low')

        # 3. Check HTF levels (CRITICAL - highest weights)
        htf_levels = self.htf_levels.get_all_levels(daily_data, weekly_data)
        htf_confluence = self.htf_levels.check_confluence(price, htf_levels, LEVEL_TOLERANCE_PCT)

        signal['htf_signals'] = htf_confluence
        signal['confluence_score'] += htf_confluence['score']
        signal['factors'].extend(htf_confluence['factors'])

        # 4. Determine if we should trade based on confluence
        signal['should_trade'] = signal['confluence_score'] >= MIN_CONFLUENCE_SCORE

        # Log if confluence insufficient
        if not signal['should_trade']:
            logger.debug(
                f"⏸️  Insufficient confluence | {symbol} | "
                f"Score: {signal['confluence_score']}/{MIN_CONFLUENCE_SCORE} | "
                f"Factors: {', '.join(signal['factors']) if signal['factors'] else 'None'} | "
                f"Price: {price:.5f}"
            )

        # 5. Apply trend filter (if enabled)
        if signal['should_trade'] and TREND_FILTER_ENABLED:
            # Calculate ADX
            data_with_adx = calculate_adx(current_data.copy(), period=ADX_PERIOD)
            latest_adx = data_with_adx.iloc[-1]

            adx_value = latest_adx['adx']
            plus_di = latest_adx['plus_di']
            minus_di = latest_adx['minus_di']

            # Check if we should trade based on trend analysis
            should_trade, trend_reason = should_trade_based_on_trend(
                adx_value=adx_value,
                plus_di=plus_di,
                minus_di=minus_di,
                candle_data=current_data,
                candle_lookback=CANDLE_LOOKBACK,
                adx_threshold=ADX_THRESHOLD,
                allow_weak_trends=ALLOW_WEAK_TRENDS
            )

            signal['trend_filter'] = {
                'adx': adx_value,
                'plus_di': plus_di,
                'minus_di': minus_di,
                'passed': should_trade,
                'reason': trend_reason
            }

            if not should_trade:
                signal['should_trade'] = False
                signal['reject_reason'] = trend_reason

                # Log why signal was blocked - helps user understand bot is working
                block_msg = (
                    f"⏸️  Signal BLOCKED by trend filter | {symbol} | "
                    f"ADX: {adx_value:.1f} | Reason: {trend_reason} | "
                    f"Confluence: {signal['confluence_score']} | "
                    f"Factors: {', '.join(signal['factors'])} | "
                    f"Price: {price:.5f}"
                )
                logger.info(block_msg)

                # Also log to signals.log
                logger.log_signal({
                    'symbol': symbol,
                    'direction': 'BLOCKED',
                    'confluence_score': signal['confluence_score'],
                    'factors': signal['factors'] + [f"ADX={adx_value:.1f}", trend_reason]
                })

                return None  # Reject signal due to trend filter

            # BREAKOUT DETECTION: Check if price broke THROUGH a confluence zone
            # This is ADDITIONAL to mean reversion - only triggers when price has momentum through levels
            breakout = self.detect_confluence_breakout(
                current_data=current_data,
                price=price,
                vwap_signals=vwap_signals,
                vp_signals=vp_signals,
                htf_levels=htf_levels,
                confluence_factors=signal['factors']
            )

            if breakout['is_breakout']:
                # BREAKOUT MODE: Price broke through confluence zone
                signal['strategy_mode'] = 'breakout'

                # FLIP DIRECTION: Trade WITH the breakout momentum
                signal['direction'] = breakout['direction']

                # STOP LOSS: At the confluence level that was broken through
                signal['stop_loss'] = breakout['broken_level']

                # TAKE PROFIT: 3R from entry (or 2R for weaker confluence)
                risk_distance = abs(price - breakout['broken_level'])
                reward_ratio = 3.0 if signal['confluence_score'] >= 7 else 2.0
                signal['reward_ratio'] = reward_ratio

                if signal['direction'] == 'buy':
                    signal['take_profit'] = price + (risk_distance * reward_ratio)
                else:
                    signal['take_profit'] = price - (risk_distance * reward_ratio)

                broken_through_str = ' → '.join(breakout['broken_through'])
                logger.info(
                    f"BREAKOUT DETECTED | {symbol} | "
                    f"Direction: {signal['direction'].upper()} | "
                    f"Broke through: {broken_through_str} | "
                    f"Entry: {price:.5f} | SL: {signal['stop_loss']:.5f} | "
                    f"TP: {signal['take_profit']:.5f} ({reward_ratio}R)"
                )

                # Log breakout signal
                logger.log_signal({
                    'symbol': symbol,
                    'direction': f"BREAKOUT_{signal['direction'].upper()}",
                    'confluence_score': signal['confluence_score'],
                    'factors': signal['factors'] + [f"Broke: {', '.join(breakout['broken_through'])}"]
                })
            else:
                # MEAN REVERSION MODE (default)
                signal['strategy_mode'] = 'mean_reversion'

        # 6. Finalize direction if not set
        if signal['should_trade'] and signal['direction'] is None:
            # Use VWAP position to determine direction
            if vwap_signals['direction'] == 'below':
                signal['direction'] = 'buy'  # Price below VWAP, buy for reversion
            else:
                signal['direction'] = 'sell'  # Price above VWAP, sell for reversion

        # Log successful signal
        if signal['should_trade']:
            success_msg = (
                f"✅ SIGNAL GENERATED | {symbol} | "
                f"Direction: {signal['direction'].upper()} | "
                f"Confluence: {signal['confluence_score']} | "
                f"Factors: {', '.join(signal['factors'])} | "
                f"Price: {price:.5f}"
            )
            logger.info(success_msg)

            # Also log to signals.log
            logger.log_signal({
                'symbol': symbol,
                'direction': signal['direction'],
                'confluence_score': signal['confluence_score'],
                'factors': signal['factors']
            })

        return signal if signal['should_trade'] else None

    def detect_breakout_momentum(
        self,
        data: pd.DataFrame,
        vwap_signals: Dict
    ) -> Dict:
        """
        Detect if price is breaking out (momentum) vs mean reverting

        Breakout conditions (BLOCK mean reversion):
        - 4+ of last 5 candles aligned in same direction
        - Candles moving AWAY from VWAP (not towards)

        Args:
            data: Price data with VWAP
            vwap_signals: VWAP signal dict from get_signals()

        Returns:
            Dict with breakout analysis
        """
        # Get last 5 candles for momentum analysis
        last_5 = data.tail(5)

        # Count bullish vs bearish candles
        bullish_candles = (last_5['close'] > last_5['open']).sum()
        bearish_candles = (last_5['close'] < last_5['open']).sum()

        # Determine momentum strength
        if bullish_candles >= 4:  # 80%+ bullish
            momentum = 'strong_bullish'
            aligned = True
            confidence = bullish_candles
        elif bearish_candles >= 4:  # 80%+ bearish
            momentum = 'strong_bearish'
            aligned = True
            confidence = bearish_candles
        else:
            momentum = 'mixed'
            aligned = False
            confidence = max(bullish_candles, bearish_candles)

        # Check direction relative to VWAP
        price_direction = vwap_signals['direction']  # 'above' or 'below'

        # Determine if moving AWAY from VWAP (breakout) or TOWARDS (reversion)
        if price_direction == 'below':
            # Price below VWAP
            # If bearish momentum → moving further DOWN (away from VWAP) = breakout
            # If bullish momentum → moving UP towards VWAP = reversion
            moving_away = (momentum == 'strong_bearish')
        else:
            # Price above VWAP
            # If bullish momentum → moving further UP (away from VWAP) = breakout
            # If bearish momentum → moving DOWN towards VWAP = reversion
            moving_away = (momentum == 'strong_bullish')

        # Breakout detected if candles aligned AND moving away from VWAP
        is_breakout = aligned and moving_away

        return {
            'is_breakout': is_breakout,
            'momentum': momentum,
            'aligned': aligned,
            'moving_away': moving_away,
            'confidence': confidence,
            'price_direction': price_direction
        }

    def check_exit_signal(
        self,
        position: Dict,
        current_data: pd.DataFrame
    ) -> bool:
        """
        Check if position should be closed (VWAP reversion)

        Args:
            position: Position dict with entry info
            current_data: Current H1 data with VWAP

        Returns:
            bool: True if should exit
        """
        if 'vwap' not in current_data.columns:
            current_data = self.vwap.calculate(current_data)

        latest = current_data.iloc[-1]
        current_price = latest['close']
        vwap = latest['vwap']

        if pd.isna(vwap):
            return False

        entry_price = position['price_open']
        position_type = position['type']

        # Check VWAP reversion
        if position_type == 'buy':
            # For buy positions, exit when price reaches VWAP from below
            if entry_price < vwap and current_price >= vwap:
                return True
        else:
            # For sell positions, exit when price reaches VWAP from above
            if entry_price > vwap and current_price <= vwap:
                return True

        return False

    def analyze_signal_strength(self, signal: Dict) -> str:
        """
        Analyze signal strength based on confluence score

        Args:
            signal: Signal dict from detect_signal()

        Returns:
            str: 'weak', 'medium', 'strong', 'very_strong'
        """
        score = signal['confluence_score']

        if score >= 10:
            return 'very_strong'
        elif score >= 7:
            return 'strong'
        elif score >= 5:
            return 'medium'
        elif score >= MIN_CONFLUENCE_SCORE:
            return 'weak'
        else:
            return 'no_signal'

    def get_signal_summary(self, signal: Optional[Dict]) -> str:
        """
        Get human-readable signal summary

        Args:
            signal: Signal dict or None

        Returns:
            str: Formatted signal summary
        """
        if signal is None:
            return "No signal detected"

        strength = self.analyze_signal_strength(signal)

        summary = []
        summary.append(f"🎯 Signal: {signal['direction'].upper()}")
        summary.append(f"   Symbol: {signal['symbol']}")
        summary.append(f"   Price: {signal['price']:.5f}")
        summary.append(f"   Confluence Score: {signal['confluence_score']} ({strength})")
        summary.append(f"   Factors ({len(signal['factors'])}):")

        for factor in signal['factors']:
            summary.append(f"     • {factor}")

        return '\n'.join(summary)

    def filter_signals_by_session(
        self,
        signals: List[Dict],
        current_time: datetime
    ) -> List[Dict]:
        """
        Filter signals by trading session

        Args:
            signals: List of detected signals
            current_time: Current datetime

        Returns:
            List of filtered signals
        """
        from config.strategy_config import TRADE_SESSIONS

        hour = current_time.hour
        day_of_week = current_time.weekday()

        # Check if in trading hours
        in_session = False

        for session_name, session_config in TRADE_SESSIONS.items():
            if not session_config['enabled']:
                continue

            start_hour = int(session_config['start'].split(':')[0])
            end_hour = int(session_config['end'].split(':')[0])

            # Handle sessions that cross midnight
            if start_hour > end_hour:
                if hour >= start_hour or hour < end_hour:
                    in_session = True
                    break
            else:
                if start_hour <= hour < end_hour:
                    in_session = True
                    break

        if not in_session:
            return []

        # Check day of week
        from config.strategy_config import TRADE_DAYS
        if day_of_week not in TRADE_DAYS:
            return []

        return signals

    def rank_signals(self, signals: List[Dict]) -> List[Dict]:
        """
        Rank signals by confluence score

        Args:
            signals: List of signals

        Returns:
            List of signals sorted by score (highest first)
        """
        return sorted(signals, key=lambda x: x['confluence_score'], reverse=True)

    def detect_confluence_breakout(
        self,
        current_data: pd.DataFrame,
        price: float,
        vwap_signals: Dict,
        vp_signals: Dict,
        htf_levels: Dict,
        confluence_factors: List[str]
    ) -> Dict:
        """
        Detect STACKED breakout confluences:
        1. Price broke THROUGH multiple confluence levels (demonstrates strength)
        2. Price now AT a strong confluence zone (entry point with backing)
        3. Stacking = High confidence breakout trade

        Example: Price breaks through VWAP Band 1 → Band 2 → arrives at Band 3 + LVN

        This is NOT random - it's looking for demonstrated momentum THROUGH levels
        combined with arrival AT a new strong confluence for entry.

        Args:
            current_data: H1 data with indicators
            price: Current price
            vwap_signals: VWAP signals dict
            vp_signals: Volume profile signals dict
            htf_levels: Higher timeframe levels dict
            confluence_factors: List of detected confluence factors

        Returns:
            Dict with breakout info: is_breakout, direction, broken_level, broken_factor
        """
        # Get last 10 candles to check for breakthrough
        lookback_candles = min(10, len(current_data))
        recent_candles = current_data.tail(lookback_candles)

        if len(recent_candles) < 5:
            return {'is_breakout': False}

        latest = recent_candles.iloc[-1]
        current_price = price

        # Step 1: Check candle momentum (need 3+ aligned candles for breakout)
        last_5 = recent_candles.tail(5)
        bullish_candles = (last_5['close'] > last_5['open']).sum()
        bearish_candles = (last_5['close'] < last_5['open']).sum()

        has_bullish_momentum = bullish_candles >= 3
        has_bearish_momentum = bearish_candles >= 3

        if not (has_bullish_momentum or has_bearish_momentum):
            # No clear momentum
            return {'is_breakout': False}

        # Step 2: Build list of all confluence levels to check for breakthrough
        confluence_levels = self._build_confluence_levels(
            latest, vwap_signals, vp_signals, htf_levels, current_price
        )

        # Step 3: Check which levels were broken through in recent candles
        levels_broken_through = []

        for candle_row in recent_candles.itertuples():
            candle_high = candle_row.high
            candle_low = candle_row.low
            i = candle_row.Index

            for level_info in confluence_levels:
                level = level_info['level']
                tolerance = level_info['tolerance']

                # Check if candle broke through this level
                if has_bullish_momentum:
                    # Bullish breakout: candle broke UP through level
                    if candle_low < (level - tolerance) and candle_high > (level + tolerance):
                        levels_broken_through.append({
                            'level': level,
                            'factor': level_info['factor'],
                            'candle_index': i
                        })
                        break
                else:
                    # Bearish breakout: candle broke DOWN through level
                    if candle_high > (level + tolerance) and candle_low < (level - tolerance):
                        levels_broken_through.append({
                            'level': level,
                            'factor': level_info['factor'],
                            'candle_index': i
                        })
                        break

        # Step 3: Check if we broke through MULTIPLE levels (demonstrates strength)
        if len(levels_broken_through) < 2:
            # Need to break through at least 2 levels to show real momentum
            return {'is_breakout': False}

        # Step 4: Check if price is NOW AT a strong confluence zone (arrival point)
        # This should be from the CURRENT confluence factors detected
        arrival_confluences = self._check_arrival_confluence(
            current_price,
            latest,
            vwap_signals,
            vp_signals,
            htf_levels,
            confluence_factors
        )

        if not arrival_confluences['has_confluence']:
            # Broke through levels but didn't arrive at a strong confluence
            return {'is_breakout': False}

        # Step 5: STACKED BREAKOUT DETECTED!
        # - Broke through 2+ levels (momentum)
        # - Arrived at strong confluence (entry point)
        # - Enter WITH momentum, SL at arrival confluence

        direction = 'buy' if has_bullish_momentum else 'sell'

        return {
            'is_breakout': True,
            'direction': direction,
            'broken_level': arrival_confluences['entry_level'],  # SL at arrival confluence
            'broken_factor': arrival_confluences['arrival_factors'],
            'levels_broken_count': len(levels_broken_through),
            'broken_through': [f"{b['factor']} @ {b['level']:.5f}" for b in levels_broken_through],
            'momentum_candles': bullish_candles if has_bullish_momentum else bearish_candles
        }

    def _build_confluence_levels(
        self,
        latest: pd.Series,
        vwap_signals: Dict,
        vp_signals: Dict,
        htf_levels: Dict,
        current_price: float
    ) -> List[Dict]:
        """Build list of all confluence levels to check for breakthroughs"""
        confluence_levels = []

        # 1. VWAP bands
        if 'vwap' in latest and not pd.isna(latest['vwap']):
            vwap = latest['vwap']
            if 'vwap_std' in latest and not pd.isna(latest['vwap_std']):
                std = latest['vwap_std']
                confluence_levels.extend([
                    {'level': vwap + std, 'factor': 'VWAP +1σ', 'tolerance': std * 0.2},
                    {'level': vwap - std, 'factor': 'VWAP -1σ', 'tolerance': std * 0.2},
                    {'level': vwap + (2 * std), 'factor': 'VWAP +2σ', 'tolerance': std * 0.2},
                    {'level': vwap - (2 * std), 'factor': 'VWAP -2σ', 'tolerance': std * 0.2},
                    {'level': vwap + (3 * std), 'factor': 'VWAP +3σ', 'tolerance': std * 0.2},
                    {'level': vwap - (3 * std), 'factor': 'VWAP -3σ', 'tolerance': std * 0.2},
                ])

        # 2. Volume Profile levels
        for key, factor in [('poc', 'POC'), ('vah', 'VAH'), ('val', 'VAL')]:
            if vp_signals.get(key):
                level = vp_signals[key]
                confluence_levels.append({
                    'level': level,
                    'factor': factor,
                    'tolerance': level * (LEVEL_TOLERANCE_PCT / 100)
                })

        # 3. LVN/HVN levels
        if vp_signals.get('lvn_levels'):
            for lvn in vp_signals['lvn_levels']:
                if abs(current_price - lvn) / current_price < 0.05:  # Within 5%
                    confluence_levels.append({
                        'level': lvn,
                        'factor': 'LVN',
                        'tolerance': lvn * (LEVEL_TOLERANCE_PCT / 100)
                    })

        if vp_signals.get('hvn_levels'):
            for hvn in vp_signals['hvn_levels']:
                if abs(current_price - hvn) / current_price < 0.05:  # Within 5%
                    confluence_levels.append({
                        'level': hvn,
                        'factor': 'HVN',
                        'tolerance': hvn * (LEVEL_TOLERANCE_PCT / 100)
                    })

        # 4. HTF levels
        for level_name, level_price in htf_levels.items():
            if level_price and not pd.isna(level_price):
                if abs(current_price - level_price) / current_price < 0.05:
                    confluence_levels.append({
                        'level': level_price,
                        'factor': level_name,
                        'tolerance': level_price * (LEVEL_TOLERANCE_PCT / 100)
                    })

        return confluence_levels

    def _check_arrival_confluence(
        self,
        current_price: float,
        latest: pd.Series,
        vwap_signals: Dict,
        vp_signals: Dict,
        htf_levels: Dict,
        confluence_factors: List[str]
    ) -> Dict:
        """
        Check if current price is AT a strong confluence zone (arrival point)

        Strong arrival zones:
        - VWAP Band 3 (extreme deviation)
        - LVN (low volume node - price accelerates through)
        - HVN (high volume node - strong S/R)
        - HTF level alignment
        - Multiple factors stacked at current price
        """
        arrival_factors = []
        entry_level = current_price

        # Check VWAP Band 3 (extreme deviation - strong reversal/continuation point)
        if 'vwap' in latest and 'vwap_std' in latest:
            vwap = latest['vwap']
            std = latest['vwap_std']

            band_3_upper = vwap + (3 * std)
            band_3_lower = vwap - (3 * std)
            tolerance = std * 0.3

            if abs(current_price - band_3_upper) < tolerance:
                arrival_factors.append('VWAP +3σ')
                entry_level = band_3_upper
            elif abs(current_price - band_3_lower) < tolerance:
                arrival_factors.append('VWAP -3σ')
                entry_level = band_3_lower

        # Check LVN (critical for breakouts - price gaps where momentum accelerates)
        if vp_signals.get('lvn_levels'):
            for lvn in vp_signals['lvn_levels']:
                if abs(current_price - lvn) / current_price < 0.005:  # Very close (0.5%)
                    arrival_factors.append('LVN')
                    entry_level = lvn
                    break

        # Check HVN (high volume zones - strong confluence)
        if vp_signals.get('hvn_levels'):
            for hvn in vp_signals['hvn_levels']:
                if abs(current_price - hvn) / current_price < 0.005:
                    arrival_factors.append('HVN')
                    entry_level = hvn
                    break

        # Check HTF levels (previous day/week levels)
        for level_name, level_price in htf_levels.items():
            if level_price and not pd.isna(level_price):
                if abs(current_price - level_price) / current_price < 0.003:  # Very close
                    arrival_factors.append(level_name)
                    entry_level = level_price
                    break

        # Require at least 1 strong arrival factor (or 2+ regular confluence factors already detected)
        has_strong_arrival = len(arrival_factors) > 0
        has_stacked_confluence = len(confluence_factors) >= 2  # From main detection

        has_confluence = has_strong_arrival or has_stacked_confluence

        return {
            'has_confluence': has_confluence,
            'arrival_factors': ', '.join(arrival_factors) if arrival_factors else 'Stacked Confluence',
            'entry_level': entry_level,
            'factor_count': len(arrival_factors)
        }
