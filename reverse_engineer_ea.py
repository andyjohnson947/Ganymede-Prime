"""
Complete EA Reverse Engineering Tool
Analyzes each trade against market conditions to deduce entry/exit rules
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ea_mining import EAMonitor


def analyze_trade_entry_conditions(trade, market_data_df, indicators_df):
    """
    Analyze exact market conditions when trade was entered

    Returns:
        Dict with all market state at entry moment
    """
    try:
        entry_time = pd.to_datetime(trade.get('entry_time'))
        if entry_time is None:
            return None
    except Exception as e:
        print(f"Warning: Could not parse entry time: {e}")
        return None

    # Find the exact bar where trade entered
    # Try exact match first
    exact_bar = market_data_df[market_data_df.index == entry_time]

    if exact_bar.empty:
        # Find nearest bar (within 60 minutes for H1 data)
        # This tolerance ensures we catch trades that happen between hourly candles
        time_diffs = abs(market_data_df.index - entry_time)
        nearest_idx = time_diffs.argmin()

        # Handle TimedeltaIndex properly - use direct indexing, not .iloc
        min_time_diff = time_diffs[nearest_idx]

        # Use 60-minute tolerance for H1 bars (matches timeframe)
        if min_time_diff < pd.Timedelta(minutes=60):
            exact_bar = market_data_df.iloc[[nearest_idx]]
        else:
            return None

    if exact_bar.empty:
        return None

    bar = exact_bar.iloc[0]

    try:
        bar_idx = market_data_df.index.get_loc(exact_bar.index[0])
    except Exception as e:
        print(f"Warning: Could not locate bar index: {e}")
        return None

    # Get previous bars for context
    prev_bars = market_data_df.iloc[max(0, bar_idx-5):bar_idx]
    lookback_bars = market_data_df.iloc[max(0, bar_idx-100):bar_idx]  # For swing detection

    # Detect swing highs/lows in last 100 bars
    swing_high = lookback_bars['high'].max() if len(lookback_bars) > 0 else None
    swing_low = lookback_bars['low'].min() if len(lookback_bars) > 0 else None

    # Find nearest swing levels
    at_swing_high = abs(bar['close'] - swing_high) < (bar['close'] * 0.001) if swing_high else False  # Within 0.1%
    at_swing_low = abs(bar['close'] - swing_low) < (bar['close'] * 0.001) if swing_low else False

    # VWAP analysis with deviation bands
    vwap_distance = None
    vwap_std_1 = None
    vwap_std_2 = None
    vwap_std_3 = None
    in_vwap_band_1 = False
    in_vwap_band_2 = False
    in_vwap_band_3 = False

    try:
        if 'VWAP' in bar and pd.notna(bar['VWAP']) and bar['VWAP'] != 0 and len(lookback_bars) > 20:
            vwap_distance = ((bar['close'] - bar['VWAP']) / bar['VWAP'] * 100)

            # Calculate VWAP standard deviation bands
            vwap_values = lookback_bars['close']
            vwap_mean = bar['VWAP']
            vwap_std = vwap_values.std()

            if pd.notna(vwap_std) and vwap_std > 0:
                vwap_std_1 = vwap_std * 1
                vwap_std_2 = vwap_std * 2
                vwap_std_3 = vwap_std * 3

                # Check which band current price is in
                price_distance_from_vwap = abs(bar['close'] - vwap_mean)
                if price_distance_from_vwap <= vwap_std_1:
                    in_vwap_band_1 = True
                elif price_distance_from_vwap <= vwap_std_2:
                    in_vwap_band_2 = True
                elif price_distance_from_vwap <= vwap_std_3:
                    in_vwap_band_3 = True
    except Exception as e:
        pass  # Silently skip VWAP analysis if it fails

    # Volume Profile analysis - POC, VAH, VAL
    volume_percentile = None
    volume_poc = None  # Point of Control - price with highest volume
    volume_vah = None  # Value Area High - upper 70% volume boundary
    volume_val = None  # Value Area Low - lower 70% volume boundary
    at_poc = False
    above_vah = False
    below_val = False

    try:
        if 'tick_volume' in bar and pd.notna(bar['tick_volume']) and len(lookback_bars) > 50:
            # Calculate volume percentile (simple high volume detection)
            volume_percentile = (lookback_bars['tick_volume'] <= bar['tick_volume']).sum() / len(lookback_bars) * 100

            # Calculate Volume Profile POC, VAH, VAL
            # Group bars by price levels and sum volume at each level
            price_min = lookback_bars['low'].min()
            price_max = lookback_bars['high'].max()
            price_range = price_max - price_min

            if price_range > 0:
                # Create price bins (50 levels)
                num_bins = 50
                bin_size = price_range / num_bins
                volume_at_price = {}

                # Aggregate volume at each price level
                for _, candle in lookback_bars.iterrows():
                    # For each candle, distribute its volume across the price range it covers
                    candle_low = candle['low']
                    candle_high = candle['high']
                    candle_volume = candle['tick_volume']

                    # Find which bins this candle overlaps
                    low_bin = int((candle_low - price_min) / bin_size)
                    high_bin = int((candle_high - price_min) / bin_size)

                    # Distribute volume evenly across bins
                    bins_covered = max(1, high_bin - low_bin + 1)
                    volume_per_bin = candle_volume / bins_covered

                    for bin_idx in range(low_bin, high_bin + 1):
                        if bin_idx < 0 or bin_idx >= num_bins:
                            continue
                        if bin_idx not in volume_at_price:
                            volume_at_price[bin_idx] = 0
                        volume_at_price[bin_idx] += volume_per_bin

                # Find POC (Point of Control - highest volume level)
                if volume_at_price:
                    poc_bin = max(volume_at_price, key=volume_at_price.get)
                    volume_poc = price_min + (poc_bin * bin_size) + (bin_size / 2)

                    # Calculate VAH and VAL (70% value area)
                    total_volume = sum(volume_at_price.values())
                    target_volume = total_volume * 0.70

                    # Sort bins by volume (descending)
                    sorted_bins = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)

                    # Accumulate volume until we hit 70%
                    accumulated_volume = 0
                    value_area_bins = []
                    for bin_idx, vol in sorted_bins:
                        value_area_bins.append(bin_idx)
                        accumulated_volume += vol
                        if accumulated_volume >= target_volume:
                            break

                    # VAH is highest price in value area, VAL is lowest
                    if value_area_bins:
                        volume_vah = price_min + (max(value_area_bins) * bin_size) + bin_size
                        volume_val = price_min + (min(value_area_bins) * bin_size)

                    # Check if current price is at POC, above VAH, or below VAL
                    if volume_poc:
                        at_poc = abs(bar['close'] - volume_poc) < (bar['close'] * 0.002)  # Within 0.2%
                    if volume_vah:
                        above_vah = bar['close'] > volume_vah
                    if volume_val:
                        below_val = bar['close'] < volume_val
    except Exception as e:
        pass  # Silently skip Volume Profile analysis if it fails

    # Low Volume Node (LVN) detection - opposite of POC
    at_lvn = False
    lvn_price = None
    lvn_percentile = None

    try:
        if 'tick_volume' in bar and pd.notna(bar['tick_volume']) and len(lookback_bars) > 50:
            # Find low volume nodes (price levels with least volume)
            if volume_at_price:
                # Find LVN (lowest volume level)
                lvn_bin = min(volume_at_price, key=volume_at_price.get)
                lvn_price = price_min + (lvn_bin * bin_size) + (bin_size / 2)

                # Check if current price is at LVN
                if lvn_price:
                    at_lvn = abs(bar['close'] - lvn_price) < (bar['close'] * 0.002)  # Within 0.2%

                # Calculate volume percentile at this price level
                current_bin = int((bar['close'] - price_min) / bin_size)
                if 0 <= current_bin < num_bins and current_bin in volume_at_price:
                    total_volume = sum(volume_at_price.values())
                    current_level_volume = volume_at_price[current_bin]
                    # Percentile = how many levels have less volume
                    levels_with_less_volume = sum(1 for v in volume_at_price.values() if v < current_level_volume)
                    lvn_percentile = (levels_with_less_volume / len(volume_at_price)) * 100
    except Exception as e:
        pass  # Silently skip LVN analysis if it fails

    # Order block detection (large volume candle followed by reversal)
    order_block_bullish = False
    order_block_bearish = False
    if len(lookback_bars) >= 3:
        for i in range(len(lookback_bars) - 3, len(lookback_bars)):
            if i < 0:
                continue
            candle = lookback_bars.iloc[i]
            volume_threshold = lookback_bars['tick_volume'].quantile(0.8)

            # Bullish order block: High volume down candle followed by reversal up
            if (candle['tick_volume'] > volume_threshold and
                candle['close'] < candle['open'] and
                i < len(lookback_bars) - 1):
                next_candle = lookback_bars.iloc[i + 1]
                if next_candle['close'] > next_candle['open']:
                    # Check if current price is near this level
                    if abs(bar['close'] - candle['low']) < (bar['close'] * 0.002):  # Within 0.2%
                        order_block_bullish = True

            # Bearish order block: High volume up candle followed by reversal down
            if (candle['tick_volume'] > volume_threshold and
                candle['close'] > candle['open'] and
                i < len(lookback_bars) - 1):
                next_candle = lookback_bars.iloc[i + 1]
                if next_candle['close'] < next_candle['open']:
                    # Check if current price is near this level
                    if abs(bar['close'] - candle['high']) < (bar['close'] * 0.002):  # Within 0.2%
                        order_block_bearish = True

    # Liquidity sweep detection (stop hunt - quick spike then reversal)
    liquidity_sweep = False
    if len(prev_bars) >= 2:
        prev1 = prev_bars.iloc[-1]
        prev2 = prev_bars.iloc[-2] if len(prev_bars) >= 2 else None

        if prev2 is not None:
            # Look for spike above resistance then immediate reversal down
            recent_high = lookback_bars['high'].max()
            if (prev1['high'] > recent_high and
                prev1['close'] < prev1['open'] and
                bar['close'] < prev1['close']):
                liquidity_sweep = True

            # Or spike below support then immediate reversal up
            recent_low = lookback_bars['low'].min()
            if (prev1['low'] < recent_low and
                prev1['close'] > prev1['open'] and
                bar['close'] > prev1['close']):
                liquidity_sweep = True

    # Fair value gap (FVG) detection - price imbalance/gap
    fair_value_gap_up = False
    fair_value_gap_down = False
    fvg_size = None

    if len(prev_bars) >= 3:
        candle1 = prev_bars.iloc[-3]
        candle2 = prev_bars.iloc[-2]
        candle3 = prev_bars.iloc[-1]

        # Bullish FVG: Gap up (candle1 high < candle3 low)
        if candle1['high'] < candle3['low']:
            gap_size = candle3['low'] - candle1['high']
            fvg_size = (gap_size / bar['close']) * 100
            # Check if current price is in the gap
            if candle1['high'] <= bar['close'] <= candle3['low']:
                fair_value_gap_up = True

        # Bearish FVG: Gap down (candle1 low > candle3 high)
        if candle1['low'] > candle3['high']:
            gap_size = candle1['low'] - candle3['high']
            fvg_size = (gap_size / bar['close']) * 100
            # Check if current price is in the gap
            if candle3['high'] <= bar['close'] <= candle1['low']:
                fair_value_gap_down = True

    conditions = {
        'entry_time': entry_time,
        'entry_price': trade.get('entry_price', 0),
        'trade_type': trade.get('trade_type', 'unknown'),
        'volume': trade.get('volume', 0),
        'tp': trade.get('tp', None),
        'sl': trade.get('sl', None),
        'exit_price': trade.get('exit_price', None),
        'exit_time': trade.get('exit_time', None),
        'profit': trade.get('profit', None),

        # Current bar OHLC
        'bar_open': bar['open'],
        'bar_high': bar['high'],
        'bar_low': bar['low'],
        'bar_close': bar['close'],
        'bar_volume': bar.get('tick_volume', 0),

        # Price position
        'price_vs_open': ((bar['close'] - bar['open']) / bar['open'] * 100) if bar['open'] != 0 else 0,

        # Indicators at entry
        'rsi_14': bar.get('RSI_14', None),
        'macd': bar.get('MACD', None),
        'macd_signal': bar.get('MACD_signal', None),
        'macd_histogram': bar.get('MACD_histogram', None),
        'sma_20': bar.get('SMA_20', None),
        'sma_50': bar.get('SMA_50', None),
        'ema_20': bar.get('EMA_20', None),
        'bb_upper': bar.get('BB_upper', None),
        'bb_middle': bar.get('BB_middle', None),
        'bb_lower': bar.get('BB_lower', None),
        'atr_14': bar.get('ATR_14', None),

        # Price position relative to indicators
        'price_vs_sma20': ((bar['close'] - bar.get('SMA_20', bar['close'])) / bar['close'] * 100) if 'SMA_20' in bar and bar['SMA_20'] else None,
        'price_vs_sma50': ((bar['close'] - bar.get('SMA_50', bar['close'])) / bar['close'] * 100) if 'SMA_50' in bar and bar['SMA_50'] else None,

        # Trend detection (using MA slopes)
        'sma20_slope': None,
        'sma50_slope': None,

        # Previous bar momentum
        'prev_bar_direction': 'up' if len(prev_bars) > 0 and prev_bars.iloc[-1]['close'] > prev_bars.iloc[-1]['open'] else 'down',
        'consecutive_up_bars': 0,
        'consecutive_down_bars': 0,

        # Market structure
        'swing_high': swing_high,
        'swing_low': swing_low,
        'at_swing_high': at_swing_high,
        'at_swing_low': at_swing_low,
        'distance_to_swing_high': ((swing_high - bar['close']) / bar['close'] * 100) if swing_high else None,
        'distance_to_swing_low': ((bar['close'] - swing_low) / bar['close'] * 100) if swing_low else None,

        # VWAP analysis
        'vwap': bar.get('VWAP', None),
        'vwap_distance_pct': vwap_distance,
        'above_vwap': vwap_distance > 0 if vwap_distance else None,
        'vwap_std_1': vwap_std_1,
        'vwap_std_2': vwap_std_2,
        'vwap_std_3': vwap_std_3,
        'in_vwap_band_1': in_vwap_band_1,
        'in_vwap_band_2': in_vwap_band_2,
        'in_vwap_band_3': in_vwap_band_3,

        # Volume Profile analysis
        'volume_percentile': volume_percentile,
        'high_volume_area': volume_percentile > 80 if volume_percentile else None,
        'volume_poc': volume_poc,
        'volume_vah': volume_vah,
        'volume_val': volume_val,
        'at_poc': at_poc,
        'above_vah': above_vah,
        'below_val': below_val,

        # Low Volume Node (LVN) analysis
        'lvn_price': lvn_price,
        'at_lvn': at_lvn,
        'lvn_percentile': lvn_percentile,
        'low_volume_area': lvn_percentile < 20 if lvn_percentile else None,

        # Order blocks
        'order_block_bullish': order_block_bullish,
        'order_block_bearish': order_block_bearish,

        # Liquidity sweeps
        'liquidity_sweep': liquidity_sweep,

        # Fair value gaps
        'fair_value_gap_up': fair_value_gap_up,
        'fair_value_gap_down': fair_value_gap_down,
        'fvg_size_pct': fvg_size,
    }

    # Calculate MA slopes if enough history
    if bar_idx >= 5 and 'SMA_20' in bar:
        sma20_prev = market_data_df.iloc[bar_idx-5].get('SMA_20')
        if sma20_prev and bar.get('SMA_20'):
            conditions['sma20_slope'] = (bar['SMA_20'] - sma20_prev) / 5

    if bar_idx >= 5 and 'SMA_50' in bar:
        sma50_prev = market_data_df.iloc[bar_idx-5].get('SMA_50')
        if sma50_prev and bar.get('SMA_50'):
            conditions['sma50_slope'] = (bar['SMA_50'] - sma50_prev) / 5

    # Count consecutive directional bars
    up_count = 0
    down_count = 0
    for i in range(len(prev_bars)-1, -1, -1):
        prev = prev_bars.iloc[i]
        if prev['close'] > prev['open']:
            up_count += 1
            if down_count > 0:
                break
        elif prev['close'] < prev['open']:
            down_count += 1
            if up_count > 0:
                break

    conditions['consecutive_up_bars'] = up_count
    conditions['consecutive_down_bars'] = down_count

    # Calculate previous day levels
    at_prev_poc = False
    at_prev_vah = False
    at_prev_val = False
    at_prev_vwap = False
    at_prev_lvn = False

    try:
        from datetime import timedelta

        entry_date = entry_time.date()
        prev_date = entry_date - timedelta(days=1)

        # Handle weekends - look back up to 5 days
        max_lookback = 5
        prev_day_data = pd.DataFrame()

        for i in range(max_lookback):
            # Get data from previous day
            prev_day_start = pd.Timestamp(prev_date)
            prev_day_end = prev_day_start + timedelta(days=1)

            prev_day_data = market_data_df[
                (market_data_df.index >= prev_day_start) &
                (market_data_df.index < prev_day_end)
            ]

            if not prev_day_data.empty:
                break

            prev_date = prev_date - timedelta(days=1)

        if not prev_day_data.empty and len(prev_day_data) > 10:
            tolerance = bar['close'] * 0.003  # 0.3% tolerance

            # Calculate previous day VWAP
            if 'VWAP' in prev_day_data.columns:
                prev_vwap = prev_day_data['VWAP'].iloc[-1]  # End of day VWAP
                if pd.notna(prev_vwap) and abs(bar['close'] - prev_vwap) < tolerance:
                    at_prev_vwap = True

            # Calculate previous day Volume Profile
            price_min = prev_day_data['low'].min()
            price_max = prev_day_data['high'].max()
            price_range = price_max - price_min

            if price_range > 0:
                num_bins = 50
                bin_size = price_range / num_bins
                volume_at_price = {}

                for _, candle in prev_day_data.iterrows():
                    candle_low = candle['low']
                    candle_high = candle['high']
                    candle_volume = candle.get('tick_volume', 0)

                    low_bin = int((candle_low - price_min) / bin_size)
                    high_bin = int((candle_high - price_min) / bin_size)
                    bins_covered = max(1, high_bin - low_bin + 1)
                    volume_per_bin = candle_volume / bins_covered

                    for bin_idx in range(low_bin, high_bin + 1):
                        if 0 <= bin_idx < num_bins:
                            if bin_idx not in volume_at_price:
                                volume_at_price[bin_idx] = 0
                            volume_at_price[bin_idx] += volume_per_bin

                if volume_at_price:
                    # Previous day POC
                    poc_bin = max(volume_at_price, key=volume_at_price.get)
                    prev_poc = price_min + (poc_bin * bin_size) + (bin_size / 2)
                    if abs(bar['close'] - prev_poc) < tolerance:
                        at_prev_poc = True

                    # Previous day VAH/VAL
                    total_volume = sum(volume_at_price.values())
                    target_volume = total_volume * 0.70
                    sorted_bins = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
                    accumulated_volume = 0
                    value_area_bins = []

                    for bin_idx, vol in sorted_bins:
                        value_area_bins.append(bin_idx)
                        accumulated_volume += vol
                        if accumulated_volume >= target_volume:
                            break

                    if value_area_bins:
                        prev_vah = price_min + (max(value_area_bins) * bin_size) + bin_size
                        prev_val = price_min + (min(value_area_bins) * bin_size)

                        if abs(bar['close'] - prev_vah) < tolerance:
                            at_prev_vah = True
                        if abs(bar['close'] - prev_val) < tolerance:
                            at_prev_val = True

                    # Previous day LVN
                    lvn_bin = min(volume_at_price, key=volume_at_price.get)
                    prev_lvn = price_min + (lvn_bin * bin_size) + (bin_size / 2)
                    if abs(bar['close'] - prev_lvn) < tolerance:
                        at_prev_lvn = True

    except Exception as e:
        pass  # Silently skip previous day analysis if it fails

    # Add previous day level flags to conditions
    conditions['at_prev_poc'] = at_prev_poc
    conditions['at_prev_vah'] = at_prev_vah
    conditions['at_prev_val'] = at_prev_val
    conditions['at_prev_vwap'] = at_prev_vwap
    conditions['at_prev_lvn'] = at_prev_lvn

    return conditions


def find_trade_patterns(all_trades_conditions):
    """
    Cluster trades by similar conditions to find entry rules
    """
    if not all_trades_conditions:
        return {}

    df = pd.DataFrame(all_trades_conditions)

    patterns = {
        'buy_patterns': [],
        'sell_patterns': [],
        'grid_rules': [],
        'exit_rules': []
    }

    # Analyze BUY entries
    buy_trades = df[df['trade_type'] == 'buy']
    if not buy_trades.empty:
        # RSI patterns
        buy_with_rsi = buy_trades[buy_trades['rsi_14'].notna()]
        if not buy_with_rsi.empty:
            avg_rsi = buy_with_rsi['rsi_14'].mean()
            min_rsi = buy_with_rsi['rsi_14'].min()
            max_rsi = buy_with_rsi['rsi_14'].max()

            if avg_rsi < 40:
                patterns['buy_patterns'].append({
                    'rule': f"BUY when RSI < {avg_rsi:.0f}",
                    'confidence': len(buy_with_rsi[buy_with_rsi['rsi_14'] < 40]) / len(buy_with_rsi),
                    'sample_size': len(buy_with_rsi)
                })

        # MACD patterns
        buy_with_macd = buy_trades[(buy_trades['macd'].notna()) & (buy_trades['macd_signal'].notna())]
        if not buy_with_macd.empty:
            macd_bullish = buy_with_macd[buy_with_macd['macd'] > buy_with_macd['macd_signal']]
            if len(macd_bullish) > len(buy_with_macd) * 0.6:
                patterns['buy_patterns'].append({
                    'rule': "BUY when MACD crosses above signal",
                    'confidence': len(macd_bullish) / len(buy_with_macd),
                    'sample_size': len(buy_with_macd)
                })

        # Price vs MA patterns
        buy_with_sma = buy_trades[buy_trades['price_vs_sma20'].notna()]
        if not buy_with_sma.empty:
            below_sma = buy_with_sma[buy_with_sma['price_vs_sma20'] < 0]
            if len(below_sma) > len(buy_with_sma) * 0.6:
                patterns['buy_patterns'].append({
                    'rule': "BUY when price below SMA(20)",
                    'confidence': len(below_sma) / len(buy_with_sma),
                    'sample_size': len(buy_with_sma)
                })

        # Swing low patterns
        buy_at_swing_low = buy_trades[buy_trades['at_swing_low'] == True]
        if len(buy_at_swing_low) > len(buy_trades) * 0.4:
            patterns['buy_patterns'].append({
                'rule': "BUY at swing lows (support)",
                'confidence': len(buy_at_swing_low) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # VWAP patterns
        buy_below_vwap = buy_trades[(buy_trades['above_vwap'] == False) & (buy_trades['vwap_distance_pct'].notna())]
        if len(buy_below_vwap) > len(buy_trades) * 0.5:
            avg_distance = buy_below_vwap['vwap_distance_pct'].mean()
            patterns['buy_patterns'].append({
                'rule': f"BUY below VWAP (avg {avg_distance:.1f}% below)",
                'confidence': len(buy_below_vwap) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # VWAP deviation band patterns - FOCUS ON BANDS 1 & 2 FOR MEAN REVERSION
        buy_at_vwap_1sd = buy_trades[buy_trades['in_vwap_band_1'] == True]
        if len(buy_at_vwap_1sd) > len(buy_trades) * 0.2:
            patterns['buy_patterns'].append({
                'rule': "🎯 BUY at VWAP -1σ band (tight mean reversion)",
                'confidence': len(buy_at_vwap_1sd) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        buy_at_vwap_2sd = buy_trades[buy_trades['in_vwap_band_2'] == True]
        if len(buy_at_vwap_2sd) > len(buy_trades) * 0.2:
            patterns['buy_patterns'].append({
                'rule': "🎯 BUY at VWAP -2σ band (strong mean reversion)",
                'confidence': len(buy_at_vwap_2sd) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        buy_at_vwap_3sd = buy_trades[buy_trades['in_vwap_band_3'] == True]
        if len(buy_at_vwap_3sd) > len(buy_trades) * 0.15:
            patterns['buy_patterns'].append({
                'rule': "BUY at VWAP -3σ band (extreme deviation)",
                'confidence': len(buy_at_vwap_3sd) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # Combined VWAP band patterns with other market structure
        buy_vwap_band_1_or_2 = buy_trades[(buy_trades['in_vwap_band_1'] == True) | (buy_trades['in_vwap_band_2'] == True)]
        if len(buy_vwap_band_1_or_2) > 0:
            # Band 1/2 + Swing Low
            buy_vwap_plus_swing = buy_vwap_band_1_or_2[buy_vwap_band_1_or_2['at_swing_low'] == True]
            if len(buy_vwap_plus_swing) > len(buy_trades) * 0.15:
                patterns['buy_patterns'].append({
                    'rule': "🎯 BUY at VWAP Band 1/2 + SWING LOW (high probability)",
                    'confidence': len(buy_vwap_plus_swing) / len(buy_trades),
                    'sample_size': len(buy_trades)
                })

            # Band 1/2 + Order Block
            buy_vwap_plus_ob = buy_vwap_band_1_or_2[buy_vwap_band_1_or_2['order_block_bullish'] == True]
            if len(buy_vwap_plus_ob) > len(buy_trades) * 0.1:
                patterns['buy_patterns'].append({
                    'rule': "🎯 BUY at VWAP Band 1/2 + BULLISH ORDER BLOCK",
                    'confidence': len(buy_vwap_plus_ob) / len(buy_trades),
                    'sample_size': len(buy_trades)
                })

            # Band 1/2 + Below VAL
            buy_vwap_plus_val = buy_vwap_band_1_or_2[buy_vwap_band_1_or_2['below_val'] == True]
            if len(buy_vwap_plus_val) > len(buy_trades) * 0.1:
                patterns['buy_patterns'].append({
                    'rule': "🎯 BUY at VWAP Band 1/2 + BELOW VAL (oversold)",
                    'confidence': len(buy_vwap_plus_val) / len(buy_trades),
                    'sample_size': len(buy_trades)
                })

        # Volume Profile patterns
        buy_at_poc = buy_trades[buy_trades['at_poc'] == True]
        if len(buy_at_poc) > len(buy_trades) * 0.3:
            patterns['buy_patterns'].append({
                'rule': "BUY at Volume Profile POC (high volume node)",
                'confidence': len(buy_at_poc) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        buy_below_val = buy_trades[buy_trades['below_val'] == True]
        if len(buy_below_val) > len(buy_trades) * 0.4:
            patterns['buy_patterns'].append({
                'rule': "BUY below Value Area Low (VAL) - bearish extension reversal",
                'confidence': len(buy_below_val) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # High volume area patterns
        buy_high_vol = buy_trades[buy_trades['high_volume_area'] == True]
        if len(buy_high_vol) > len(buy_trades) * 0.4:
            patterns['buy_patterns'].append({
                'rule': "BUY at high volume bars",
                'confidence': len(buy_high_vol) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # Order block patterns
        buy_at_bullish_ob = buy_trades[buy_trades['order_block_bullish'] == True]
        if len(buy_at_bullish_ob) > len(buy_trades) * 0.3:
            patterns['buy_patterns'].append({
                'rule': "BUY at bullish order blocks (institutional zones)",
                'confidence': len(buy_at_bullish_ob) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # Liquidity sweep patterns
        buy_after_sweep = buy_trades[buy_trades['liquidity_sweep'] == True]
        if len(buy_after_sweep) > len(buy_trades) * 0.2:
            patterns['buy_patterns'].append({
                'rule': "BUY after liquidity sweep (stop hunt reversal)",
                'confidence': len(buy_after_sweep) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

        # Fair value gap patterns
        buy_in_fvg = buy_trades[buy_trades['fair_value_gap_up'] == True]
        if len(buy_in_fvg) > len(buy_trades) * 0.25:
            patterns['buy_patterns'].append({
                'rule': "BUY in bullish FVG (filling price gap)",
                'confidence': len(buy_in_fvg) / len(buy_trades),
                'sample_size': len(buy_trades)
            })

    # Analyze SELL entries
    sell_trades = df[df['trade_type'] == 'sell']
    if not sell_trades.empty:
        # RSI patterns
        sell_with_rsi = sell_trades[sell_trades['rsi_14'].notna()]
        if not sell_with_rsi.empty:
            avg_rsi = sell_with_rsi['rsi_14'].mean()

            if avg_rsi > 60:
                patterns['sell_patterns'].append({
                    'rule': f"SELL when RSI > {avg_rsi:.0f}",
                    'confidence': len(sell_with_rsi[sell_with_rsi['rsi_14'] > 60]) / len(sell_with_rsi),
                    'sample_size': len(sell_with_rsi)
                })

        # MACD patterns
        sell_with_macd = sell_trades[(sell_trades['macd'].notna()) & (sell_trades['macd_signal'].notna())]
        if not sell_with_macd.empty:
            macd_bearish = sell_with_macd[sell_with_macd['macd'] < sell_with_macd['macd_signal']]
            if len(macd_bearish) > len(sell_with_macd) * 0.6:
                patterns['sell_patterns'].append({
                    'rule': "SELL when MACD crosses below signal",
                    'confidence': len(macd_bearish) / len(sell_with_macd),
                    'sample_size': len(sell_with_macd)
                })

        # Swing high patterns
        sell_at_swing_high = sell_trades[sell_trades['at_swing_high'] == True]
        if len(sell_at_swing_high) > len(sell_trades) * 0.4:
            patterns['sell_patterns'].append({
                'rule': "SELL at swing highs (resistance)",
                'confidence': len(sell_at_swing_high) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # VWAP patterns
        sell_above_vwap = sell_trades[(sell_trades['above_vwap'] == True) & (sell_trades['vwap_distance_pct'].notna())]
        if len(sell_above_vwap) > len(sell_trades) * 0.5:
            avg_distance = sell_above_vwap['vwap_distance_pct'].mean()
            patterns['sell_patterns'].append({
                'rule': f"SELL above VWAP (avg {avg_distance:.1f}% above)",
                'confidence': len(sell_above_vwap) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # VWAP deviation band patterns - FOCUS ON BANDS 1 & 2 FOR MEAN REVERSION
        sell_at_vwap_1sd = sell_trades[sell_trades['in_vwap_band_1'] == True]
        if len(sell_at_vwap_1sd) > len(sell_trades) * 0.2:
            patterns['sell_patterns'].append({
                'rule': "🎯 SELL at VWAP +1σ band (tight mean reversion)",
                'confidence': len(sell_at_vwap_1sd) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        sell_at_vwap_2sd = sell_trades[sell_trades['in_vwap_band_2'] == True]
        if len(sell_at_vwap_2sd) > len(sell_trades) * 0.2:
            patterns['sell_patterns'].append({
                'rule': "🎯 SELL at VWAP +2σ band (strong mean reversion)",
                'confidence': len(sell_at_vwap_2sd) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        sell_at_vwap_3sd = sell_trades[sell_trades['in_vwap_band_3'] == True]
        if len(sell_at_vwap_3sd) > len(sell_trades) * 0.15:
            patterns['sell_patterns'].append({
                'rule': "SELL at VWAP +3σ band (extreme deviation)",
                'confidence': len(sell_at_vwap_3sd) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # Combined VWAP band patterns with other market structure
        sell_vwap_band_1_or_2 = sell_trades[(sell_trades['in_vwap_band_1'] == True) | (sell_trades['in_vwap_band_2'] == True)]
        if len(sell_vwap_band_1_or_2) > 0:
            # Band 1/2 + Swing High
            sell_vwap_plus_swing = sell_vwap_band_1_or_2[sell_vwap_band_1_or_2['at_swing_high'] == True]
            if len(sell_vwap_plus_swing) > len(sell_trades) * 0.15:
                patterns['sell_patterns'].append({
                    'rule': "🎯 SELL at VWAP Band 1/2 + SWING HIGH (high probability)",
                    'confidence': len(sell_vwap_plus_swing) / len(sell_trades),
                    'sample_size': len(sell_trades)
                })

            # Band 1/2 + Order Block
            sell_vwap_plus_ob = sell_vwap_band_1_or_2[sell_vwap_band_1_or_2['order_block_bearish'] == True]
            if len(sell_vwap_plus_ob) > len(sell_trades) * 0.1:
                patterns['sell_patterns'].append({
                    'rule': "🎯 SELL at VWAP Band 1/2 + BEARISH ORDER BLOCK",
                    'confidence': len(sell_vwap_plus_ob) / len(sell_trades),
                    'sample_size': len(sell_trades)
                })

            # Band 1/2 + Above VAH
            sell_vwap_plus_vah = sell_vwap_band_1_or_2[sell_vwap_band_1_or_2['above_vah'] == True]
            if len(sell_vwap_plus_vah) > len(sell_trades) * 0.1:
                patterns['sell_patterns'].append({
                    'rule': "🎯 SELL at VWAP Band 1/2 + ABOVE VAH (overbought)",
                    'confidence': len(sell_vwap_plus_vah) / len(sell_trades),
                    'sample_size': len(sell_trades)
                })

        # Volume Profile patterns
        sell_at_poc = sell_trades[sell_trades['at_poc'] == True]
        if len(sell_at_poc) > len(sell_trades) * 0.3:
            patterns['sell_patterns'].append({
                'rule': "SELL at Volume Profile POC (high volume node)",
                'confidence': len(sell_at_poc) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        sell_above_vah = sell_trades[sell_trades['above_vah'] == True]
        if len(sell_above_vah) > len(sell_trades) * 0.4:
            patterns['sell_patterns'].append({
                'rule': "SELL above Value Area High (VAH) - bullish extension reversal",
                'confidence': len(sell_above_vah) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # High volume area patterns
        sell_high_vol = sell_trades[sell_trades['high_volume_area'] == True]
        if len(sell_high_vol) > len(sell_trades) * 0.4:
            patterns['sell_patterns'].append({
                'rule': "SELL at high volume bars",
                'confidence': len(sell_high_vol) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # Order block patterns
        sell_at_bearish_ob = sell_trades[sell_trades['order_block_bearish'] == True]
        if len(sell_at_bearish_ob) > len(sell_trades) * 0.3:
            patterns['sell_patterns'].append({
                'rule': "SELL at bearish order blocks (institutional zones)",
                'confidence': len(sell_at_bearish_ob) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # Liquidity sweep patterns
        sell_after_sweep = sell_trades[sell_trades['liquidity_sweep'] == True]
        if len(sell_after_sweep) > len(sell_trades) * 0.2:
            patterns['sell_patterns'].append({
                'rule': "SELL after liquidity sweep (stop hunt reversal)",
                'confidence': len(sell_after_sweep) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

        # Fair value gap patterns
        sell_in_fvg = sell_trades[sell_trades['fair_value_gap_down'] == True]
        if len(sell_in_fvg) > len(sell_trades) * 0.25:
            patterns['sell_patterns'].append({
                'rule': "SELL in bearish FVG (filling price gap)",
                'confidence': len(sell_in_fvg) / len(sell_trades),
                'sample_size': len(sell_trades)
            })

    return patterns


def analyze_price_behavior_at_level(all_trades_conditions, market_data_df, level_field, level_name):
    """
    UNIVERSAL price behavior analysis for ANY level
    Analyzes if price continues through or reverses at a given level

    Args:
        level_field: The field name to check (e.g., 'at_poc', 'at_lvn', 'in_vwap_band_1')
        level_name: Display name for the level (e.g., 'POC', 'LVN', 'VWAP Band 1')
    """
    if not all_trades_conditions:
        return {}

    df = pd.DataFrame(all_trades_conditions)

    analysis = {
        'total_trades': len(df),
        'trades_at_level': 0,
        'continuation': 0,
        'reversal': 0,
        'buy_at_level': 0,
        'sell_at_level': 0,
        'reactions': []
    }

    # Analyze trades at this level
    trades_at_level = df[df[level_field] == True]
    analysis['trades_at_level'] = len(trades_at_level)

    if len(trades_at_level) > 0:
        analysis['buy_at_level'] = len(trades_at_level[trades_at_level['trade_type'] == 'buy'])
        analysis['sell_at_level'] = len(trades_at_level[trades_at_level['trade_type'] == 'sell'])

        # Analyze price reaction after hitting level
        for _, trade in trades_at_level.iterrows():
            entry_time = pd.to_datetime(trade['entry_time'])
            entry_price = trade['entry_price']
            trade_type = trade['trade_type']

            # Look at next 5-10 bars to see if price continued or reversed
            try:
                if entry_time in market_data_df.index:
                    bar_idx = market_data_df.index.get_loc(entry_time)
                    if bar_idx < len(market_data_df) - 10:
                        next_bars = market_data_df.iloc[bar_idx+1:bar_idx+11]

                        # Calculate price movement
                        price_change = (next_bars['close'].iloc[-1] - entry_price) / entry_price * 100

                        # Determine if continuation or reversal
                        if trade_type == 'buy':
                            # For buy, continuation = price went up, reversal = price went down
                            if price_change > 0.1:
                                analysis['continuation'] += 1
                                reaction = 'continuation_up'
                            elif price_change < -0.1:
                                analysis['reversal'] += 1
                                reaction = 'reversal_down'
                            else:
                                reaction = 'neutral'
                        else:  # sell
                            # For sell, continuation = price went down, reversal = price went up
                            if price_change < -0.1:
                                analysis['continuation'] += 1
                                reaction = 'continuation_down'
                            elif price_change > 0.1:
                                analysis['reversal'] += 1
                                reaction = 'reversal_up'
                            else:
                                reaction = 'neutral'

                        analysis['reactions'].append({
                            'entry_time': entry_time,
                            'entry_price': entry_price,
                            'trade_type': trade_type,
                            'price_change_pct': price_change,
                            'reaction': reaction,
                            'level_name': level_name
                        })
            except Exception as e:
                pass  # Skip if there's any issue with this trade

    return analysis


def analyze_all_level_reactions(all_trades_conditions, market_data_df):
    """
    Analyze price behavior at ALL key levels:
    - POC, VAH, VAL
    - VWAP Bands 1, 2, 3
    - Swing Highs/Lows
    - Order Blocks (Bullish/Bearish)
    - LVN
    """
    if not all_trades_conditions:
        return {}

    all_reactions = {}

    # Define all levels to analyze
    levels_to_analyze = [
        ('at_poc', 'POC (Point of Control)'),
        ('above_vah', 'Above VAH'),
        ('below_val', 'Below VAL'),
        ('in_vwap_band_1', 'VWAP Band 1 (1σ)'),
        ('in_vwap_band_2', 'VWAP Band 2 (2σ)'),
        ('in_vwap_band_3', 'VWAP Band 3 (3σ)'),
        ('at_swing_high', 'Swing High'),
        ('at_swing_low', 'Swing Low'),
        ('order_block_bullish', 'Bullish Order Block'),
        ('order_block_bearish', 'Bearish Order Block'),
        ('at_lvn', 'LVN (Low Volume Node)'),
    ]

    for level_field, level_name in levels_to_analyze:
        analysis = analyze_price_behavior_at_level(
            all_trades_conditions,
            market_data_df,
            level_field,
            level_name
        )

        if analysis and analysis['trades_at_level'] > 0:
            all_reactions[level_name] = analysis

    return all_reactions


def analyze_entry_times(all_trades_conditions):
    """
    Analyze what times the EA prefers to enter trades
    """
    if not all_trades_conditions:
        return {}

    df = pd.DataFrame(all_trades_conditions)

    time_analysis = {
        'total_trades': len(df),
        'hourly_distribution': {},
        'day_of_week_distribution': {},
        'peak_hours': [],
        'quiet_hours': [],
        'session_distribution': {}
    }

    # Extract hour and day of week
    df['hour'] = pd.to_datetime(df['entry_time']).dt.hour
    df['day_of_week'] = pd.to_datetime(df['entry_time']).dt.day_name()

    # Hourly distribution
    hourly_counts = df['hour'].value_counts().sort_index()
    for hour, count in hourly_counts.items():
        time_analysis['hourly_distribution'][hour] = {
            'count': int(count),
            'percentage': float(count / len(df) * 100)
        }

    # Find peak hours (top 25% of activity)
    avg_hourly = len(df) / 24
    peak_threshold = avg_hourly * 1.5
    for hour, data in time_analysis['hourly_distribution'].items():
        if data['count'] > peak_threshold:
            time_analysis['peak_hours'].append(hour)
        elif data['count'] < avg_hourly * 0.5:
            time_analysis['quiet_hours'].append(hour)

    # Day of week distribution
    dow_counts = df['day_of_week'].value_counts()
    for day, count in dow_counts.items():
        time_analysis['day_of_week_distribution'][day] = {
            'count': int(count),
            'percentage': float(count / len(df) * 100)
        }

    # Trading session distribution (approximate)
    def get_session(hour):
        if 0 <= hour < 8:
            return 'Asian'
        elif 8 <= hour < 16:
            return 'London'
        elif 16 <= hour < 24:
            return 'New York'
        return 'Unknown'

    df['session'] = df['hour'].apply(get_session)
    session_counts = df['session'].value_counts()
    for session, count in session_counts.items():
        time_analysis['session_distribution'][session] = {
            'count': int(count),
            'percentage': float(count / len(df) * 100)
        }

    return time_analysis


def analyze_vwap_mean_reversion(all_trades_conditions):
    """
    Dedicated VWAP bands 1 & 2 mean reversion analysis
    """
    if not all_trades_conditions:
        return {}

    df = pd.DataFrame(all_trades_conditions)

    vwap_analysis = {
        'total_trades': len(df),
        'band_1_trades': 0,
        'band_2_trades': 0,
        'band_3_trades': 0,
        'band_1_2_trades': 0,
        'buy_band_1': 0,
        'buy_band_2': 0,
        'sell_band_1': 0,
        'sell_band_2': 0,
        'band_1_2_percentage': 0,
        'avg_deviation_band_1': 0,
        'avg_deviation_band_2': 0
    }

    # Count trades at each band
    band_1_trades = df[df['in_vwap_band_1'] == True]
    band_2_trades = df[df['in_vwap_band_2'] == True]
    band_3_trades = df[df['in_vwap_band_3'] == True]
    band_1_2_trades = df[(df['in_vwap_band_1'] == True) | (df['in_vwap_band_2'] == True)]

    vwap_analysis['band_1_trades'] = len(band_1_trades)
    vwap_analysis['band_2_trades'] = len(band_2_trades)
    vwap_analysis['band_3_trades'] = len(band_3_trades)
    vwap_analysis['band_1_2_trades'] = len(band_1_2_trades)
    vwap_analysis['band_1_2_percentage'] = (len(band_1_2_trades) / len(df) * 100) if len(df) > 0 else 0

    # Buy/Sell breakdown for bands 1 & 2
    buy_trades = df[df['trade_type'] == 'buy']
    sell_trades = df[df['trade_type'] == 'sell']

    vwap_analysis['buy_band_1'] = len(buy_trades[buy_trades['in_vwap_band_1'] == True])
    vwap_analysis['buy_band_2'] = len(buy_trades[buy_trades['in_vwap_band_2'] == True])
    vwap_analysis['sell_band_1'] = len(sell_trades[sell_trades['in_vwap_band_1'] == True])
    vwap_analysis['sell_band_2'] = len(sell_trades[sell_trades['in_vwap_band_2'] == True])

    # Average deviation distance for bands 1 & 2
    if len(band_1_trades) > 0:
        vwap_analysis['avg_deviation_band_1'] = band_1_trades['vwap_distance_pct'].mean()
    if len(band_2_trades) > 0:
        vwap_analysis['avg_deviation_band_2'] = band_2_trades['vwap_distance_pct'].mean()

    # Combined patterns for bands 1 & 2
    vwap_analysis['band_1_2_at_swing'] = len(band_1_2_trades[
        (band_1_2_trades['at_swing_low'] == True) | (band_1_2_trades['at_swing_high'] == True)
    ])
    vwap_analysis['band_1_2_at_order_blocks'] = len(band_1_2_trades[
        (band_1_2_trades['order_block_bullish'] == True) | (band_1_2_trades['order_block_bearish'] == True)
    ])
    vwap_analysis['band_1_2_at_poc'] = len(band_1_2_trades[band_1_2_trades['at_poc'] == True])
    vwap_analysis['band_1_2_outside_value_area'] = len(band_1_2_trades[
        (band_1_2_trades['below_val'] == True) | (band_1_2_trades['above_vah'] == True)
    ])

    return vwap_analysis


def create_previous_daily_values_dataset(all_trades_conditions, market_data_df):
    """
    Create separate dataset showing if previous daily values (POC, VAH, VAL, VWAP, LVN)
    are used as entry levels
    """
    if not all_trades_conditions:
        return {}

    df = pd.DataFrame(all_trades_conditions)

    previous_day_analysis = {
        'total_trades_analyzed': len(df),
        'used_prev_poc': 0,
        'used_prev_vah': 0,
        'used_prev_val': 0,
        'used_prev_vwap': 0,
        'used_prev_lvn': 0,
        'examples': []
    }

    # Calculate daily values for each trading day
    market_data_df['date'] = market_data_df.index.date

    for _, trade in df.iterrows():
        entry_time = pd.to_datetime(trade['entry_time'])
        entry_price = trade['entry_price']
        entry_date = entry_time.date()

        # Get previous day's data
        prev_date = entry_date - timedelta(days=1)

        # Handle weekends - go back further if needed
        max_lookback = 5
        for i in range(max_lookback):
            prev_day_data = market_data_df[market_data_df['date'] == prev_date]
            if not prev_day_data.empty:
                break
            prev_date = prev_date - timedelta(days=1)

        if prev_day_data.empty:
            continue

        # Calculate previous day's POC, VAH, VAL, VWAP, LVN
        prev_poc = None
        prev_vah = None
        prev_val = None
        prev_vwap = None
        prev_lvn = None

        # Volume Profile for previous day
        try:
            price_min = prev_day_data['low'].min()
            price_max = prev_day_data['high'].max()
            price_range = price_max - price_min

            if price_range > 0:
                num_bins = 50
                bin_size = price_range / num_bins
                volume_at_price = {}

                for _, candle in prev_day_data.iterrows():
                    candle_low = candle['low']
                    candle_high = candle['high']
                    candle_volume = candle.get('tick_volume', 0)

                    low_bin = int((candle_low - price_min) / bin_size)
                    high_bin = int((candle_high - price_min) / bin_size)
                    bins_covered = max(1, high_bin - low_bin + 1)
                    volume_per_bin = candle_volume / bins_covered

                    for bin_idx in range(low_bin, high_bin + 1):
                        if 0 <= bin_idx < num_bins:
                            if bin_idx not in volume_at_price:
                                volume_at_price[bin_idx] = 0
                            volume_at_price[bin_idx] += volume_per_bin

                if volume_at_price:
                    # POC
                    poc_bin = max(volume_at_price, key=volume_at_price.get)
                    prev_poc = price_min + (poc_bin * bin_size) + (bin_size / 2)

                    # VAH/VAL
                    total_volume = sum(volume_at_price.values())
                    target_volume = total_volume * 0.70
                    sorted_bins = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
                    accumulated_volume = 0
                    value_area_bins = []
                    for bin_idx, vol in sorted_bins:
                        value_area_bins.append(bin_idx)
                        accumulated_volume += vol
                        if accumulated_volume >= target_volume:
                            break

                    if value_area_bins:
                        prev_vah = price_min + (max(value_area_bins) * bin_size) + bin_size
                        prev_val = price_min + (min(value_area_bins) * bin_size)

                    # LVN
                    lvn_bin = min(volume_at_price, key=volume_at_price.get)
                    prev_lvn = price_min + (lvn_bin * bin_size) + (bin_size / 2)

                # VWAP
                if 'VWAP' in prev_day_data.columns:
                    prev_vwap = prev_day_data['VWAP'].iloc[-1]  # End of day VWAP
        except Exception as e:
            pass

        # Check if entry price is near any previous day levels
        tolerance = entry_price * 0.003  # 0.3% tolerance

        used_levels = []

        if prev_poc and abs(entry_price - prev_poc) < tolerance:
            previous_day_analysis['used_prev_poc'] += 1
            used_levels.append('POC')

        if prev_vah and abs(entry_price - prev_vah) < tolerance:
            previous_day_analysis['used_prev_vah'] += 1
            used_levels.append('VAH')

        if prev_val and abs(entry_price - prev_val) < tolerance:
            previous_day_analysis['used_prev_val'] += 1
            used_levels.append('VAL')

        if prev_vwap and abs(entry_price - prev_vwap) < tolerance:
            previous_day_analysis['used_prev_vwap'] += 1
            used_levels.append('VWAP')

        if prev_lvn and abs(entry_price - prev_lvn) < tolerance:
            previous_day_analysis['used_prev_lvn'] += 1
            used_levels.append('LVN')

        if used_levels:
            previous_day_analysis['examples'].append({
                'entry_time': entry_time,
                'entry_price': entry_price,
                'trade_type': trade['trade_type'],
                'levels_used': ', '.join(used_levels),
                'prev_poc': prev_poc,
                'prev_vah': prev_vah,
                'prev_val': prev_val,
                'prev_vwap': prev_vwap,
                'prev_lvn': prev_lvn
            })

    return previous_day_analysis


def analyze_counter_trend_duration(trades_df, market_data_df):
    """
    Analyze how long counter-trend trades are left open
    """
    if trades_df.empty:
        return {}

    duration_analysis = {
        'total_counter_trend_trades': 0,
        'avg_duration_minutes': 0,
        'min_duration_minutes': None,
        'max_duration_minutes': None,
        'duration_distribution': [],
        'examples': []
    }

    # Detect trend at entry and analyze duration
    counter_trend_durations = []

    for _, trade in trades_df.iterrows():
        entry_time = pd.to_datetime(trade.get('entry_time'))
        exit_time = pd.to_datetime(trade.get('exit_time'))
        trade_type = trade.get('trade_type', 'unknown')

        if pd.isna(exit_time):
            continue

        # Get market trend at entry
        if entry_time in market_data_df.index:
            bar = market_data_df.loc[entry_time]
            trend_direction = bar.get('trend_direction', 'neutral')

            # Determine if counter-trend
            is_counter_trend = False
            if trade_type == 'buy' and trend_direction == 'downtrend':
                is_counter_trend = True
            elif trade_type == 'sell' and trend_direction == 'uptrend':
                is_counter_trend = True

            if is_counter_trend:
                duration_minutes = (exit_time - entry_time).total_seconds() / 60
                counter_trend_durations.append(duration_minutes)

                duration_analysis['examples'].append({
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'duration_minutes': duration_minutes,
                    'duration_hours': duration_minutes / 60,
                    'trade_type': trade_type,
                    'trend_direction': trend_direction,
                    'entry_price': trade.get('entry_price'),
                    'exit_price': trade.get('exit_price'),
                    'profit': trade.get('profit')
                })

    if counter_trend_durations:
        duration_analysis['total_counter_trend_trades'] = len(counter_trend_durations)
        duration_analysis['avg_duration_minutes'] = np.mean(counter_trend_durations)
        duration_analysis['min_duration_minutes'] = np.min(counter_trend_durations)
        duration_analysis['max_duration_minutes'] = np.max(counter_trend_durations)

        # Duration distribution (bucketed)
        for minutes in counter_trend_durations:
            hours = minutes / 60
            if hours < 1:
                bucket = '< 1 hour'
            elif hours < 4:
                bucket = '1-4 hours'
            elif hours < 12:
                bucket = '4-12 hours'
            elif hours < 24:
                bucket = '12-24 hours'
            else:
                bucket = '> 24 hours'

            duration_analysis['duration_distribution'].append(bucket)

    return duration_analysis


def analyze_hedging_and_recovery(trades_df):
    """
    Analyze capital recovery and hedging mechanisms
    """
    recovery_analysis = {
        'hedge_detected': False,
        'hedge_pairs': 0,
        'simultaneous_opposite_positions': 0,
        'recovery_sequences': [],
        'martingale_detected': False,
        'dca_detected': False,
        'avg_recovery_lot_multiplier': 0,
        'max_recovery_attempts': 0,
        'recovery_time_avg': None,
        'losing_trade_recovery_rate': 0,
        'hedge_timing': [],
        'hedge_triggers': []  # NEW: What triggers hedge opening
    }

    trades_df = trades_df.sort_values('entry_time').copy()

    # Detect simultaneous opposite positions (hedging) WITH TRIGGER ANALYSIS
    for i, trade1 in trades_df.iterrows():
        # Check if there are opposite direction trades within 5 minutes
        time_window_start = pd.to_datetime(trade1.get('entry_time')) - pd.Timedelta(minutes=5)
        time_window_end = pd.to_datetime(trade1.get('entry_time')) + pd.Timedelta(minutes=5)

        nearby_trades = trades_df[
            (pd.to_datetime(trades_df['entry_time']) >= time_window_start) &
            (pd.to_datetime(trades_df['entry_time']) <= time_window_end) &
            (trades_df['symbol'] == trade1.get('symbol', ''))
        ]

        # Check for opposite direction
        if trade1.get('trade_type') == 'buy':
            opposite_trades = nearby_trades[nearby_trades['trade_type'] == 'sell']
        else:
            opposite_trades = nearby_trades[nearby_trades['trade_type'] == 'buy']

        if len(opposite_trades) > 0:
            recovery_analysis['hedge_detected'] = True
            recovery_analysis['hedge_pairs'] += 1

            hedge_trade = opposite_trades.iloc[0]
            time_diff_minutes = (pd.to_datetime(hedge_trade.get('entry_time')) -
                                pd.to_datetime(trade1.get('entry_time'))).total_seconds() / 60

            # Calculate price movement and potential drawdown trigger
            entry_price1 = trade1.get('entry_price', 0)
            entry_price_hedge = hedge_trade.get('entry_price', 0)

            if entry_price1 > 0:
                if trade1.get('trade_type') == 'buy':
                    # For BUY, negative movement = drawdown
                    price_movement_pips = (entry_price_hedge - entry_price1) * 10000
                else:
                    # For SELL, positive movement = drawdown
                    price_movement_pips = (entry_price1 - entry_price_hedge) * 10000

                price_movement_pct = abs(entry_price_hedge - entry_price1) / entry_price1 * 100
            else:
                price_movement_pips = 0
                price_movement_pct = 0

            recovery_analysis['hedge_timing'].append({
                'time_diff': time_diff_minutes,
                'original_type': trade1.get('trade_type', 'unknown'),
                'hedge_type': hedge_trade.get('trade_type', 'unknown'),
                'volume_ratio': hedge_trade.get('volume', 0) / trade1.get('volume', 1) if trade1.get('volume', 0) > 0 else 0
            })

            # Detailed hedge trigger analysis
            recovery_analysis['hedge_triggers'].append({
                'original_entry': entry_price1,
                'hedge_entry': entry_price_hedge,
                'time_before_hedge_minutes': abs(time_diff_minutes),
                'price_movement_pips': price_movement_pips,
                'price_movement_pct': price_movement_pct,
                'original_volume': trade1.get('volume', 0),
                'hedge_volume': hedge_trade.get('volume', 0),
                'volume_multiplier': hedge_trade.get('volume', 0) / trade1.get('volume', 1) if trade1.get('volume', 0) > 0 else 0,
                'original_exit': trade1.get('exit_price'),
                'hedge_exit': hedge_trade.get('exit_price'),
                'original_profit': trade1.get('profit'),
                'hedge_profit': hedge_trade.get('profit'),
                'net_result': (trade1.get('profit', 0) or 0) + (hedge_trade.get('profit', 0) or 0)
            })

    # Analyze recovery sequences (adding to positions after losses)
    recovery_sequences = []

    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol].copy()

        # Track consecutive same-direction trades
        current_sequence = []

        for idx, trade in symbol_trades.iterrows():
            if not current_sequence:
                current_sequence.append(trade)
            else:
                prev_trade = current_sequence[-1]

                # Same direction within reasonable time (1 hour)
                time_diff = (pd.to_datetime(trade.get('entry_time')) -
                           pd.to_datetime(prev_trade.get('entry_time'))).total_seconds() / 3600

                if trade.get('trade_type') == prev_trade.get('trade_type') and time_diff < 1:
                    current_sequence.append(trade)
                else:
                    # Analyze completed sequence
                    if len(current_sequence) >= 2:
                        volumes = [t['volume'] for t in current_sequence]
                        prices = [t['entry_price'] for t in current_sequence]

                        # Check if adding to position (DCA/martingale)
                        is_adding_to_losing = False
                        if current_sequence[0].get('trade_type', 'unknown') == 'buy':
                            # For buys, adding when price goes down
                            is_adding_to_losing = prices[-1] < prices[0]
                        else:
                            # For sells, adding when price goes up
                            is_adding_to_losing = prices[-1] > prices[0]

                        # Check lot progression
                        volume_ratios = [volumes[i] / volumes[i-1] for i in range(1, len(volumes)) if volumes[i-1] > 0]
                        avg_volume_ratio = sum(volume_ratios) / len(volume_ratios) if volume_ratios else 1.0

                        if is_adding_to_losing:
                            recovery_sequences.append({
                                'sequence_length': len(current_sequence),
                                'avg_volume_multiplier': avg_volume_ratio,
                                'price_deterioration': abs(prices[-1] - prices[0]) / prices[0] * 100 if prices[0] != 0 else 0,
                                'is_martingale': avg_volume_ratio > 1.5,
                                'is_dca': 0.9 < avg_volume_ratio < 1.1,
                                'trade_type': current_sequence[0].get('trade_type', 'unknown')
                            })

                    current_sequence = [trade]

        # Check final sequence
        if len(current_sequence) >= 2:
            volumes = [t['volume'] for t in current_sequence]
            prices = [t['entry_price'] for t in current_sequence]

            is_adding_to_losing = False
            if current_sequence[0].get('trade_type', 'unknown') == 'buy':
                is_adding_to_losing = prices[-1] < prices[0]
            else:
                is_adding_to_losing = prices[-1] > prices[0]

            volume_ratios = [volumes[i] / volumes[i-1] for i in range(1, len(volumes)) if volumes[i-1] > 0]
            avg_volume_ratio = sum(volume_ratios) / len(volume_ratios) if volume_ratios else 1.0

            if is_adding_to_losing:
                recovery_sequences.append({
                    'sequence_length': len(current_sequence),
                    'avg_volume_multiplier': avg_volume_ratio,
                    'price_deterioration': abs(prices[-1] - prices[0]) / prices[0] * 100 if prices[0] != 0 else 0,
                    'is_martingale': avg_volume_ratio > 1.5,
                    'is_dca': 0.9 < avg_volume_ratio < 1.1,
                    'trade_type': current_sequence[0].get('trade_type', 'unknown')
                })

    recovery_analysis['recovery_sequences'] = recovery_sequences

    if recovery_sequences:
        martingale_count = sum(1 for seq in recovery_sequences if seq['is_martingale'])
        dca_count = sum(1 for seq in recovery_sequences if seq['is_dca'])

        recovery_analysis['martingale_detected'] = martingale_count > 0
        recovery_analysis['dca_detected'] = dca_count > 0
        recovery_analysis['max_recovery_attempts'] = max(seq['sequence_length'] for seq in recovery_sequences)

        all_multipliers = [seq['avg_volume_multiplier'] for seq in recovery_sequences]
        recovery_analysis['avg_recovery_lot_multiplier'] = sum(all_multipliers) / len(all_multipliers)

    return recovery_analysis


def analyze_position_management(trades_df):
    """
    Analyze grid, DCA, martingale patterns
    """
    management_rules = {
        'grid_spacing': None,
        'dca_trigger': None,
        'lot_progression': None,
        'max_positions': 0
    }

    trades_df = trades_df.sort_values('entry_time')

    # Analyze consecutive same-direction trades
    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol]

        consecutive_same_dir = []
        current_group = []

        for i, trade in symbol_trades.iterrows():
            if not current_group or trade.get('trade_type') == current_group[-1].get('trade_type'):
                current_group.append(trade)
            else:
                if len(current_group) >= 2:
                    consecutive_same_dir.append(current_group)
                current_group = [trade]

        if len(current_group) >= 2:
            consecutive_same_dir.append(current_group)

        # Analyze spacing in same-direction groups
        for group in consecutive_same_dir:
            if len(group) < 2:
                continue

            prices = [t['entry_price'] for t in group]
            volumes = [t['volume'] for t in group]

            # Calculate price spacing
            spacings = [abs(prices[i+1] - prices[i]) for i in range(len(prices)-1)]
            avg_spacing = np.mean(spacings)
            std_spacing = np.std(spacings)

            # Check if regular spacing (grid)
            if std_spacing < avg_spacing * 0.3:  # Low variance = grid
                management_rules['grid_spacing'] = avg_spacing
                management_rules['max_positions'] = max(management_rules['max_positions'], len(group))

            # Check volume progression (martingale/averaging)
            if len(volumes) >= 3:
                volume_ratios = [volumes[i+1] / volumes[i] for i in range(len(volumes)-1) if volumes[i] > 0]
                if volume_ratios:
                    avg_ratio = np.mean(volume_ratios)
                    if avg_ratio > 1.5:  # Increasing volume
                        management_rules['lot_progression'] = f"Multiplier: {avg_ratio:.2f}x"
                    elif 0.9 < avg_ratio < 1.1:  # Fixed volume
                        management_rules['lot_progression'] = "Fixed lots"

    return management_rules


def main():
    print("\n" + "=" * 80)
    print("  EA REVERSE ENGINEERING - COMPLETE ANALYSIS")
    print("=" * 80 + "\n")

    # Load configuration
    config = load_config()
    credentials = load_credentials()
    logger = setup_logging(config)

    # Create bot
    bot = MT5TradingBot(config, credentials)

    if not bot.start():
        print("❌ Failed to connect to MT5")
        return

    print("✅ Connected to MT5\n")

    # Get EA trades
    ea_monitor = EAMonitor(bot.mt5_manager, bot.storage)
    ea_monitor.start_monitoring()

    trades_df = ea_monitor.get_trades_dataframe()

    if trades_df.empty:
        print("❌ No trades found")
        bot.stop()
        return

    # Normalize column names - 'type' -> 'trade_type'
    if 'type' in trades_df.columns and 'trade_type' not in trades_df.columns:
        trades_df['trade_type'] = trades_df['type']

    print(f"📊 Analyzing {len(trades_df)} trades...\n")

    # Clean up and validate symbols
    # Remove trades with blank/invalid symbols
    trades_df['symbol'] = trades_df['symbol'].astype(str).str.strip()
    invalid_symbols = trades_df[trades_df['symbol'].isin(['', 'nan', 'None'])]

    if len(invalid_symbols) > 0:
        print(f"⚠️  Removing {len(invalid_symbols)} trades with invalid symbols")
        trades_df = trades_df[~trades_df['symbol'].isin(['', 'nan', 'None'])]

    if trades_df.empty:
        print("❌ No trades with valid symbols found")
        bot.stop()
        return

    # Get the most common symbol (in case there are multiple)
    symbol_counts = trades_df['symbol'].value_counts()
    symbol = symbol_counts.index[0]

    print(f"Symbols found: {dict(symbol_counts)}")
    print(f"Fetching market data for {symbol}...")

    # Calculate required history based on trade date range
    earliest_trade = pd.to_datetime(trades_df['entry_time']).min()
    latest_trade = pd.to_datetime(trades_df['entry_time']).max()
    days_span = (latest_trade - earliest_trade).days

    # Calculate required hourly bars (add 20% buffer + extra for indicators)
    hours_needed = int(days_span * 24 * 1.2) + 500  # 20% buffer + 500 for indicators
    bars_to_fetch = max(5000, hours_needed)  # At least 5000, more if needed

    print(f"Trade date range: {earliest_trade.date()} to {latest_trade.date()} ({days_span} days)")
    print(f"Fetching {bars_to_fetch} hourly bars to ensure ALL trades are covered...")

    # Get historical bars
    market_data = bot.collector.get_latest_data(symbol, 'H1', bars=bars_to_fetch)

    if market_data is None or market_data.empty:
        print("❌ Failed to fetch market data")
        bot.stop()
        return

    # Calculate indicators
    market_data = bot.indicator_manager.calculate_all(market_data)
    print(f"✅ Loaded {len(market_data)} bars with indicators\n")

    # Add trend detection to market data
    def detect_trend(df, period=50):
        """Detect if market is trending or ranging"""
        # ADX-like trend strength
        df['SMA_20'] = df['close'].rolling(20).mean()
        df['SMA_50'] = df['close'].rolling(50).mean()

        # Trend direction
        df['trend_direction'] = 'neutral'
        df.loc[df['SMA_20'] > df['SMA_50'], 'trend_direction'] = 'uptrend'
        df.loc[df['SMA_20'] < df['SMA_50'], 'trend_direction'] = 'downtrend'

        # Trend strength (price deviation from SMA)
        df['trend_strength'] = abs((df['close'] - df['SMA_50']) / df['SMA_50'] * 100)

        # Strong trend = > 1% deviation
        df['strong_trend'] = df['trend_strength'] > 1.0

        return df

    market_data = detect_trend(market_data)

    # Analyze each trade
    print("="*80)
    print("TRADE-BY-TRADE ANALYSIS (ALL 213 TRADES)")
    print("="*80 + "\n")

    all_conditions = []
    trades_with_trend_info = []

    for idx, trade in trades_df.iterrows():
        conditions = analyze_trade_entry_conditions(trade, market_data, market_data)

        # Get trend info even if conditions is None
        entry_time = pd.to_datetime(trade.get('entry_time'))
        trend_info = None

        if entry_time in market_data.index:
            bar = market_data.loc[entry_time]
            trend_info = {
                'entry_time': entry_time,
                'trade_type': trade.get('trade_type', 'unknown'),
                'trend_direction': bar.get('trend_direction', 'unknown'),
                'trend_strength': bar.get('trend_strength', 0),
                'strong_trend': bar.get('strong_trend', False),
                'price': trade.get('entry_price', 0)
            }
            trades_with_trend_info.append(trend_info)

        # Print basic info for ALL trades
        trade_type = trade.get('trade_type', 'unknown').upper()
        entry_price = trade.get('entry_price', 0)
        volume = trade.get('volume', 0)
        tp = trade.get('tp')
        sl = trade.get('sl')

        print(f"Trade #{idx+1}: {trade_type} @ {entry_price:.5f} | Vol: {volume:.2f}", end="")

        # Show TP/SL if available
        if tp or sl:
            tp_str = f"TP: {tp:.5f}" if tp else "No TP"
            sl_str = f"SL: {sl:.5f}" if sl else "No SL"
            print(f" | {tp_str}, {sl_str}", end="")

        if trend_info:
            trend_dir = trend_info['trend_direction']
            trend_str = trend_info['trend_strength']
            trend_icon = "📈" if trend_dir == "uptrend" else "📉" if trend_dir == "downtrend" else "↔️"
            strong_marker = " [STRONG TREND]" if trend_info['strong_trend'] else " [ranging]"
            print(f" {trend_icon} {trend_dir}{strong_marker} ({trend_str:.2f}%)")
        else:
            print(" [outside data window]")

        if conditions:
            all_conditions.append(conditions)

            # Only print detailed info for trades with full data
            print(f"  Time: {conditions['entry_time']}")

            # Indicators
            if conditions['rsi_14']:
                print(f"  RSI(14): {conditions['rsi_14']:.1f}")
            if conditions['macd'] and conditions['macd_signal']:
                print(f"  MACD: {conditions['macd']:.5f} vs Signal: {conditions['macd_signal']:.5f}")
            if conditions['price_vs_sma20']:
                print(f"  Price vs SMA(20): {conditions['price_vs_sma20']:+.2f}%")
            if conditions['price_vs_sma50']:
                print(f"  Price vs SMA(50): {conditions['price_vs_sma50']:+.2f}%")

            # Market structure
            if conditions['at_swing_high']:
                print(f"  ⚠️ AT SWING HIGH: {conditions['swing_high']:.5f}")
            elif conditions['at_swing_low']:
                print(f"  ⚠️ AT SWING LOW: {conditions['swing_low']:.5f}")
            elif conditions['distance_to_swing_high'] is not None:
                print(f"  Distance to Swing High: {conditions['distance_to_swing_high']:.2f}%")
            elif conditions['distance_to_swing_low'] is not None:
                print(f"  Distance to Swing Low: {conditions['distance_to_swing_low']:.2f}%")

            # VWAP with deviation bands - HIGHLIGHT BANDS 1 & 2
            if conditions['vwap_distance_pct'] is not None:
                vwap_pos = "above" if conditions['above_vwap'] else "below"
                vwap_output = f"  VWAP: {vwap_pos} ({conditions['vwap_distance_pct']:+.2f}%)"

                # Show which deviation band with emphasis on bands 1 & 2
                if conditions['in_vwap_band_1']:
                    vwap_output += " 🎯 [BAND 1 - TIGHT MEAN REVERSION]"
                elif conditions['in_vwap_band_2']:
                    vwap_output += " 🎯 [BAND 2 - STRONG MEAN REVERSION]"
                elif conditions['in_vwap_band_3']:
                    vwap_output += " [Within 3σ band]"
                else:
                    vwap_output += " [Beyond 3σ - EXTREME]"

                print(vwap_output)

                # Show actual deviation values
                if conditions['vwap_std_1']:
                    print(f"    1σ: ±{conditions['vwap_std_1']:.5f}, 2σ: ±{conditions['vwap_std_2']:.5f}, 3σ: ±{conditions['vwap_std_3']:.5f}")

            # Volume Profile - POC, VAH, VAL
            if conditions['volume_poc'] is not None:
                print(f"  📊 Volume Profile:")
                print(f"    POC (Point of Control): {conditions['volume_poc']:.5f}")
                if conditions['at_poc']:
                    print(f"    ⚠️ PRICE AT POC (high volume node)")

            if conditions['volume_vah'] is not None and conditions['volume_val'] is not None:
                print(f"    VAH (Value Area High): {conditions['volume_vah']:.5f}")
                print(f"    VAL (Value Area Low): {conditions['volume_val']:.5f}")

                if conditions['above_vah']:
                    print(f"    ⬆️ PRICE ABOVE VALUE AREA (bullish extension)")
                elif conditions['below_val']:
                    print(f"    ⬇️ PRICE BELOW VALUE AREA (bearish extension)")
                else:
                    print(f"    ✅ PRICE IN VALUE AREA (70% volume zone)")

            # Volume percentile
            if conditions['high_volume_area']:
                print(f"  📊 HIGH VOLUME BAR (percentile: {conditions['volume_percentile']:.0f})")

            # Low Volume Node (LVN) analysis
            if conditions['at_lvn']:
                print(f"  🔻 AT LOW VOLUME NODE (LVN): {conditions['lvn_price']:.5f}")
                print(f"     Price breakout zone - low liquidity area")
            elif conditions['low_volume_area']:
                print(f"  🔻 IN LOW VOLUME AREA (percentile: {conditions['lvn_percentile']:.0f})")

            # Order blocks
            if conditions['order_block_bullish']:
                print(f"  🟢 BULLISH ORDER BLOCK (institutional buy zone)")
            if conditions['order_block_bearish']:
                print(f"  🔴 BEARISH ORDER BLOCK (institutional sell zone)")

            # Liquidity sweeps
            if conditions['liquidity_sweep']:
                print(f"  💥 LIQUIDITY SWEEP DETECTED (stop hunt)")

            # Fair value gaps
            if conditions['fair_value_gap_up']:
                print(f"  ⬆️ BULLISH FVG: Price filling gap ({conditions['fvg_size_pct']:.2f}%)")
            if conditions['fair_value_gap_down']:
                print(f"  ⬇️ BEARISH FVG: Price filling gap ({conditions['fvg_size_pct']:.2f}%)")

            print()

    # Find patterns
    print("\n" + "="*80)
    print("DEDUCED ENTRY RULES")
    print("="*80 + "\n")

    patterns = find_trade_patterns(all_conditions)

    if patterns['buy_patterns']:
        print("BUY ENTRY CONDITIONS:")
        for p in patterns['buy_patterns']:
            print(f"  • {p['rule']}")
            print(f"    Confidence: {p['confidence']:.0%} ({p['sample_size']} trades)")
        print()

    if patterns['sell_patterns']:
        print("SELL ENTRY CONDITIONS:")
        for p in patterns['sell_patterns']:
            print(f"  • {p['rule']}")
            print(f"    Confidence: {p['confidence']:.0%} ({p['sample_size']} trades)")
        print()

    # VWAP Mean Reversion Analysis - FOCUSED ON BANDS 1 & 2
    print("\n" + "="*80)
    print("🎯 VWAP MEAN REVERSION ANALYSIS (BANDS 1 & 2 FOCUS)")
    print("="*80 + "\n")

    vwap_stats = analyze_vwap_mean_reversion(all_conditions)

    if vwap_stats and vwap_stats['total_trades'] > 0:
        print(f"Total Trades Analyzed: {vwap_stats['total_trades']}")
        print()

        print("📊 VWAP BAND DISTRIBUTION:")
        print(f"  Band 1 (1σ): {vwap_stats['band_1_trades']} trades ({vwap_stats['band_1_trades']/vwap_stats['total_trades']*100:.1f}%)")
        print(f"  Band 2 (2σ): {vwap_stats['band_2_trades']} trades ({vwap_stats['band_2_trades']/vwap_stats['total_trades']*100:.1f}%)")
        print(f"  Band 3 (3σ): {vwap_stats['band_3_trades']} trades ({vwap_stats['band_3_trades']/vwap_stats['total_trades']*100:.1f}%)")
        print(f"  🎯 Combined Bands 1 & 2: {vwap_stats['band_1_2_trades']} trades ({vwap_stats['band_1_2_percentage']:.1f}%)")
        print()

        if vwap_stats['band_1_2_trades'] > 0:
            print("🎯 MEAN REVERSION FOCUS - BANDS 1 & 2 BREAKDOWN:")
            print(f"  BUY entries at Band 1: {vwap_stats['buy_band_1']}")
            print(f"  BUY entries at Band 2: {vwap_stats['buy_band_2']}")
            print(f"  SELL entries at Band 1: {vwap_stats['sell_band_1']}")
            print(f"  SELL entries at Band 2: {vwap_stats['sell_band_2']}")
            print()

            if vwap_stats['avg_deviation_band_1'] != 0:
                print(f"  Average VWAP deviation at Band 1: {vwap_stats['avg_deviation_band_1']:+.2f}%")
            if vwap_stats['avg_deviation_band_2'] != 0:
                print(f"  Average VWAP deviation at Band 2: {vwap_stats['avg_deviation_band_2']:+.2f}%")
            print()

            print("🎯 CONFLUENCE WITH OTHER MARKET STRUCTURE (Bands 1 & 2):")
            if vwap_stats['band_1_2_at_swing'] > 0 and vwap_stats['band_1_2_trades'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_swing'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Swing Highs/Lows: {vwap_stats['band_1_2_at_swing']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_at_order_blocks'] > 0 and vwap_stats['band_1_2_trades'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_order_blocks'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Order Blocks: {vwap_stats['band_1_2_at_order_blocks']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_at_poc'] > 0 and vwap_stats['band_1_2_trades'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_poc'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Volume Profile POC: {vwap_stats['band_1_2_at_poc']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_outside_value_area'] > 0 and vwap_stats['band_1_2_trades'] > 0:
                confluence_pct = vwap_stats['band_1_2_outside_value_area'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Outside Value Area (VAH/VAL): {vwap_stats['band_1_2_outside_value_area']} ({confluence_pct:.0f}%)")
            print()

            print("💡 INTERPRETATION:")
            if vwap_stats['band_1_2_percentage'] > 50:
                print("  ✅ EA heavily uses VWAP bands 1 & 2 for mean reversion entries!")
            elif vwap_stats['band_1_2_percentage'] > 30:
                print("  ✅ EA frequently uses VWAP bands 1 & 2 as entry trigger")
            else:
                print("  ⚠️ VWAP bands 1 & 2 are NOT the primary entry strategy")

            if vwap_stats['band_1_2_at_swing'] > vwap_stats['band_1_2_trades'] * 0.4:
                print("  ✅ Strong confluence: VWAP bands + swing levels = high probability setup")

            if vwap_stats['band_1_2_outside_value_area'] > vwap_stats['band_1_2_trades'] * 0.3:
                print("  ✅ EA targets mean reversion from extended zones (outside value area)")

    # PRICE BEHAVIOR ANALYSIS AT ALL KEY LEVELS
    print("\n" + "="*80)
    print("📊 PRICE BEHAVIOR ANALYSIS AT ALL KEY LEVELS")
    print("="*80 + "\n")
    print("Analyzing if price CONTINUES or REVERSES at each institutional level...")
    print()

    all_level_reactions = analyze_all_level_reactions(all_conditions, market_data)

    if all_level_reactions:
        # Sort by number of trades for better readability
        sorted_levels = sorted(all_level_reactions.items(),
                             key=lambda x: x[1]['trades_at_level'],
                             reverse=True)

        for level_name, stats in sorted_levels:
            print(f"📍 {level_name.upper()}")
            print(f"  Trades at this level: {stats['trades_at_level']}")
            print(f"  BUY entries: {stats['buy_at_level']} | SELL entries: {stats['sell_at_level']}")

            if stats['continuation'] > 0 or stats['reversal'] > 0:
                total_reactions = stats['continuation'] + stats['reversal']
                cont_pct = stats['continuation'] / total_reactions * 100 if total_reactions > 0 else 0
                rev_pct = stats['reversal'] / total_reactions * 100 if total_reactions > 0 else 0

                print(f"  📊 PRICE BEHAVIOR:")
                print(f"     Continuation: {stats['continuation']} trades ({cont_pct:.1f}%)")
                print(f"     Reversal: {stats['reversal']} trades ({rev_pct:.1f}%)")

                # Interpretation
                if cont_pct > 65:
                    print(f"     ✅ Price BREAKS THROUGH {level_name} - weak resistance/support")
                elif rev_pct > 65:
                    print(f"     🔄 Price REVERSES at {level_name} - strong resistance/support")
                else:
                    print(f"     🟡 Mixed behavior at {level_name} - context-dependent")

                # Show example
                if stats['reactions'] and len(stats['reactions']) > 0:
                    example = stats['reactions'][0]
                    print(f"     Example: {example['trade_type'].upper()} @ {example['entry_price']:.5f} → {example['reaction']}")

            print()

        # Summary statistics
        print("="*80)
        print("💡 SUMMARY INSIGHTS:")
        print()

        # Find strongest reversal levels (support/resistance)
        reversal_levels = [(name, stats['reversal'] / (stats['continuation'] + stats['reversal']) if (stats['continuation'] + stats['reversal']) > 0 else 0)
                          for name, stats in all_level_reactions.items()
                          if (stats['continuation'] + stats['reversal']) >= 3]  # At least 3 reactions
        reversal_levels.sort(key=lambda x: x[1], reverse=True)

        if reversal_levels and reversal_levels[0][1] > 0.6:
            print(f"🔄 STRONGEST REVERSAL ZONES (act as support/resistance):")
            for name, pct in reversal_levels[:3]:
                if pct > 0.6:
                    print(f"   • {name}: {pct*100:.0f}% reversal rate")

        # Find strongest breakout levels (continuation)
        continuation_levels = [(name, stats['continuation'] / (stats['continuation'] + stats['reversal']) if (stats['continuation'] + stats['reversal']) > 0 else 0)
                             for name, stats in all_level_reactions.items()
                             if (stats['continuation'] + stats['reversal']) >= 3]
        continuation_levels.sort(key=lambda x: x[1], reverse=True)

        if continuation_levels and continuation_levels[0][1] > 0.6:
            print()
            print(f"⚡ STRONGEST BREAKOUT ZONES (price continues through):")
            for name, pct in continuation_levels[:3]:
                if pct > 0.6:
                    print(f"   • {name}: {pct*100:.0f}% continuation rate")

    else:
        print("  No level reaction data available")

    # ENTRY TIME PATTERN ANALYSIS
    print("\n" + "="*80)
    print("🕐 ENTRY TIME PATTERN ANALYSIS")
    print("="*80 + "\n")

    time_stats = analyze_entry_times(all_conditions)

    if time_stats and time_stats['total_trades'] > 0:
        print(f"Total Trades Analyzed: {time_stats['total_trades']}")
        print()

        # Trading session distribution
        if time_stats['session_distribution']:
            print("📊 TRADING SESSION DISTRIBUTION:")
            for session, data in sorted(time_stats['session_distribution'].items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"  {session}: {data['count']} trades ({data['percentage']:.1f}%)")
            print()

            # Interpretation
            sessions_sorted = sorted(time_stats['session_distribution'].items(), key=lambda x: x[1]['count'], reverse=True)
            if sessions_sorted:
                top_session = sessions_sorted[0]
                print(f"💡 PREFERRED SESSION: {top_session[0]} ({top_session[1]['percentage']:.1f}% of trades)")

        # Peak hours
        if time_stats['peak_hours']:
            print()
            print(f"⏰ PEAK TRADING HOURS (high activity):")
            peak_hours_sorted = sorted(time_stats['peak_hours'])
            for hour in peak_hours_sorted:
                count = time_stats['hourly_distribution'][hour]['count']
                pct = time_stats['hourly_distribution'][hour]['percentage']
                print(f"  {hour:02d}:00 - {count} trades ({pct:.1f}%)")

        # Quiet hours
        if time_stats['quiet_hours']:
            print()
            print(f"😴 QUIET HOURS (low activity):")
            quiet_hours_sorted = sorted(time_stats['quiet_hours'])
            for hour in quiet_hours_sorted:
                count = time_stats['hourly_distribution'][hour]['count']
                pct = time_stats['hourly_distribution'][hour]['percentage']
                print(f"  {hour:02d}:00 - {count} trades ({pct:.1f}%)")

        # Day of week
        if time_stats['day_of_week_distribution']:
            print()
            print("📅 DAY OF WEEK DISTRIBUTION:")
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day in day_order:
                if day in time_stats['day_of_week_distribution']:
                    data = time_stats['day_of_week_distribution'][day]
                    print(f"  {day}: {data['count']} trades ({data['percentage']:.1f}%)")

    # PREVIOUS DAILY VALUES ANALYSIS
    print("\n" + "="*80)
    print("📊 PREVIOUS DAILY VALUES AS ENTRY LEVELS")
    print("="*80 + "\n")

    prev_day_stats = create_previous_daily_values_dataset(all_conditions, market_data)

    if prev_day_stats and prev_day_stats['total_trades_analyzed'] > 0:
        print(f"Total Trades Analyzed: {prev_day_stats['total_trades_analyzed']}")
        print()

        total_using_prev_levels = (prev_day_stats['used_prev_poc'] +
                                    prev_day_stats['used_prev_vah'] +
                                    prev_day_stats['used_prev_val'] +
                                    prev_day_stats['used_prev_vwap'] +
                                    prev_day_stats['used_prev_lvn'])

        print("📊 USAGE OF PREVIOUS DAY LEVELS:")
        print(f"  Previous POC: {prev_day_stats['used_prev_poc']} trades ({prev_day_stats['used_prev_poc']/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print(f"  Previous VAH: {prev_day_stats['used_prev_vah']} trades ({prev_day_stats['used_prev_vah']/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print(f"  Previous VAL: {prev_day_stats['used_prev_val']} trades ({prev_day_stats['used_prev_val']/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print(f"  Previous VWAP: {prev_day_stats['used_prev_vwap']} trades ({prev_day_stats['used_prev_vwap']/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print(f"  Previous LVN: {prev_day_stats['used_prev_lvn']} trades ({prev_day_stats['used_prev_lvn']/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print()
        print(f"  Total using any previous day level: {total_using_prev_levels} ({total_using_prev_levels/prev_day_stats['total_trades_analyzed']*100:.1f}%)")
        print()

        print("💡 INTERPRETATION:")
        if total_using_prev_levels > prev_day_stats['total_trades_analyzed'] * 0.3:
            print("  ✅ EA HEAVILY USES previous day levels for entries!")
            print("  Previous day institutional levels (POC, VAH, VAL) are key entry zones")
        elif total_using_prev_levels > prev_day_stats['total_trades_analyzed'] * 0.15:
            print("  🟡 EA MODERATELY uses previous day levels")
            print("  Previous levels provide confluence for some entries")
        else:
            print("  ⚠️ EA does NOT primarily use previous day levels")
            print("  Entries are based on real-time market conditions")

        # Show examples
        if prev_day_stats['examples']:
            print()
            print("📋 EXAMPLES OF ENTRIES AT PREVIOUS DAY LEVELS:")
            for idx, example in enumerate(prev_day_stats['examples'][:5], 1):
                print(f"  {idx}. {example['trade_type'].upper()} @ {example['entry_price']:.5f}")
                print(f"     Time: {example['entry_time']}")
                print(f"     Previous day levels used: {example['levels_used']}")
                if 'POC' in example['levels_used']:
                    print(f"       Prev POC: {example['prev_poc']:.5f}")
                if 'VAH' in example['levels_used']:
                    print(f"       Prev VAH: {example['prev_vah']:.5f}")
                if 'VAL' in example['levels_used']:
                    print(f"       Prev VAL: {example['prev_val']:.5f}")
                if 'VWAP' in example['levels_used']:
                    print(f"       Prev VWAP: {example['prev_vwap']:.5f}")
                if 'LVN' in example['levels_used']:
                    print(f"       Prev LVN: {example['prev_lvn']:.5f}")

    # COUNTER-TREND DURATION ANALYSIS
    print("\n" + "="*80)
    print("⏱️ COUNTER-TREND TRADE DURATION ANALYSIS")
    print("="*80 + "\n")

    ct_duration_stats = analyze_counter_trend_duration(trades_df, market_data)

    if ct_duration_stats and ct_duration_stats['total_counter_trend_trades'] > 0:
        print(f"Total Counter-Trend Trades: {ct_duration_stats['total_counter_trend_trades']}")
        print()

        avg_hours = ct_duration_stats['avg_duration_minutes'] / 60
        min_hours = ct_duration_stats['min_duration_minutes'] / 60
        max_hours = ct_duration_stats['max_duration_minutes'] / 60

        print(f"📊 DURATION STATISTICS:")
        print(f"  Average: {avg_hours:.1f} hours ({ct_duration_stats['avg_duration_minutes']:.0f} minutes)")
        print(f"  Minimum: {min_hours:.1f} hours ({ct_duration_stats['min_duration_minutes']:.0f} minutes)")
        print(f"  Maximum: {max_hours:.1f} hours ({ct_duration_stats['max_duration_minutes']:.0f} minutes)")
        print()

        # Duration distribution
        if ct_duration_stats['duration_distribution']:
            from collections import Counter
            dist_counts = Counter(ct_duration_stats['duration_distribution'])

            print("📊 DURATION DISTRIBUTION:")
            for bucket in ['< 1 hour', '1-4 hours', '4-12 hours', '12-24 hours', '> 24 hours']:
                if bucket in dist_counts:
                    count = dist_counts[bucket]
                    pct = count / ct_duration_stats['total_counter_trend_trades'] * 100
                    print(f"  {bucket}: {count} trades ({pct:.1f}%)")
            print()

        print("💡 INTERPRETATION:")
        if avg_hours < 2:
            print("  ✅ QUICK EXITS: EA closes counter-trend trades quickly (< 2 hours avg)")
            print("  Strategy: Scalping or quick reversals")
        elif avg_hours < 12:
            print("  🟡 MEDIUM HOLD: EA holds counter-trend trades for several hours")
            print("  Strategy: Intraday mean reversion")
        else:
            print("  ⚠️ LONG HOLD: EA holds counter-trend trades for extended periods")
            print("  ⚠️ RISK: Extended exposure against trend can be risky")

        # Show examples
        if ct_duration_stats['examples']:
            print()
            print("📋 COUNTER-TREND TRADE EXAMPLES:")
            for idx, example in enumerate(ct_duration_stats['examples'][:5], 1):
                profit_sign = "+" if example['profit'] and example['profit'] > 0 else ""
                profit_str = f"${profit_sign}{example['profit']:.2f}" if example['profit'] else "N/A"
                print(f"  {idx}. {example['trade_type'].upper()} against {example['trend_direction']}")
                print(f"     Entry: {example['entry_price']:.5f} @ {example['entry_time']}")
                print(f"     Exit:  {example['exit_price']:.5f} @ {example['exit_time']}")
                print(f"     Duration: {example['duration_hours']:.1f} hours")
                print(f"     Profit: {profit_str}")

    else:
        print("  No counter-trend trades detected or no closed trades to analyze")

    # CAPITAL RECOVERY & HEDGING ANALYSIS
    print("\n" + "="*80)
    print("💰 CAPITAL RECOVERY & HEDGING MECHANISMS")
    print("="*80 + "\n")

    recovery_analysis = analyze_hedging_and_recovery(trades_df)

    # Hedging Analysis
    if recovery_analysis['hedge_detected']:
        print("🔄 HEDGING STRATEGY DETECTED!")
        print(f"  Hedge pairs found: {recovery_analysis['hedge_pairs'] // 2}")
        print(f"  Total opposite position entries: {recovery_analysis['hedge_pairs']}")
        print()

        if recovery_analysis['hedge_timing']:
            print("  📊 Hedge Timing Analysis:")
            avg_time_diff = sum(abs(h['time_diff']) for h in recovery_analysis['hedge_timing']) / len(recovery_analysis['hedge_timing'])
            print(f"    Average time between hedge entries: {avg_time_diff:.1f} minutes")

            volume_ratios = [h['volume_ratio'] for h in recovery_analysis['hedge_timing']]
            avg_volume_ratio = sum(volume_ratios) / len(volume_ratios)
            print(f"    Average hedge volume ratio: {avg_volume_ratio:.2f}x")

            if avg_volume_ratio > 1.2:
                print(f"    ⚠️ UNBALANCED HEDGE: Hedge positions are {avg_volume_ratio:.1f}x larger")
            elif 0.9 < avg_volume_ratio < 1.1:
                print(f"    ✅ BALANCED HEDGE: Equal volume on both sides")
            else:
                print(f"    ⚠️ PARTIAL HEDGE: Hedge positions are {avg_volume_ratio:.1f}x of original")

            # Show hedge examples
            print("\n  📋 Hedge Examples:")
            for idx, hedge in enumerate(recovery_analysis['hedge_timing'][:3], 1):
                print(f"    {idx}. {hedge['original_type'].upper()} → {hedge['hedge_type'].upper()}")
                print(f"       Time gap: {abs(hedge['time_diff']):.1f} min, Volume ratio: {hedge['volume_ratio']:.2f}x")

        # HEDGE TRIGGER ANALYSIS - What causes hedge to open?
        if recovery_analysis['hedge_triggers']:
            print("\n  🔍 HEDGE TRIGGER ANALYSIS:")
            print("  " + "="*70)

            triggers = recovery_analysis['hedge_triggers']

            # Analyze trigger patterns
            avg_time = sum(t['time_before_hedge_minutes'] for t in triggers) / len(triggers)
            avg_price_move_pips = sum(abs(t['price_movement_pips']) for t in triggers) / len(triggers)
            avg_price_move_pct = sum(t['price_movement_pct'] for t in triggers) / len(triggers)

            print(f"\n  📊 HEDGE OPENING TRIGGERS:")
            print(f"    Average time before hedge: {avg_time:.1f} minutes")
            print(f"    Average price movement: {avg_price_move_pips:.1f} pips ({avg_price_move_pct:.2f}%)")

            # Determine trigger type
            if avg_time < 1:
                print(f"    ⚡ IMMEDIATE HEDGE: Opens simultaneously with original trade")
                print(f"    💡 Trigger: Likely based on ENTRY SIGNAL or time-based strategy")
            elif avg_time < 30:
                print(f"    ⏱️ QUICK HEDGE: Opens within {avg_time:.0f} minutes")
                print(f"    💡 Trigger: Likely DRAWDOWN or pip-based ({avg_price_move_pips:.0f} pips)")
            else:
                print(f"    ⏰ DELAYED HEDGE: Opens after {avg_time:.0f} minutes")
                print(f"    💡 Trigger: Time-based or large drawdown")

            # Check for consistent trigger patterns
            pip_movements = [abs(t['price_movement_pips']) for t in triggers]
            pip_std = pd.Series(pip_movements).std()

            if pip_std < 5 and avg_price_move_pips < 5:
                print(f"    ✅ CONSISTENT PATTERN: Hedge opens at similar pip levels")
                print(f"       Likely drawdown trigger: ~{avg_price_move_pips:.0f} pips in loss")
            elif avg_time < 1:
                print(f"    ✅ SIMULTANEOUS PATTERN: Both positions opened together")
                print(f"       Strategy: Lock-in spread or double-entry strategy")

            # Analyze hedge closing mechanism
            closed_hedges = [t for t in triggers if t['original_exit'] and t['hedge_exit']]

            if closed_hedges:
                print(f"\n  📊 HEDGE CLOSING MECHANISM:")

                # Check if hedges close together
                simultaneous_close = 0
                staggered_close = 0
                winners = 0
                losers = 0

                for t in closed_hedges:
                    net_result = t['net_result']

                    if net_result > 0:
                        winners += 1
                    else:
                        losers += 1

                    # Check if they closed at same time (would need exit times)
                    # For now, check net result pattern

                print(f"    Total closed hedge pairs analyzed: {len(closed_hedges)}")
                print(f"    Net profitable hedges: {winners} ({winners/len(closed_hedges)*100:.0f}%)")
                print(f"    Net losing hedges: {losers} ({losers/len(closed_hedges)*100:.0f}%)")

                avg_net = sum(t['net_result'] for t in closed_hedges) / len(closed_hedges)
                print(f"    Average net result per hedge: ${avg_net:.2f}")

                if avg_net > 0:
                    print(f"    ✅ HEDGING IS PROFITABLE: Avg +${avg_net:.2f} per pair")
                elif avg_net > -5:
                    print(f"    🟡 HEDGING REDUCES LOSS: Limits drawdown effectively")
                else:
                    print(f"    ⚠️ HEDGING IS COSTLY: Avg -${abs(avg_net):.2f} per pair")

            # Show detailed examples
            print(f"\n  📋 DETAILED HEDGE TRIGGER EXAMPLES:")
            for idx, t in enumerate(triggers[:3], 1):
                print(f"\n    Example {idx}:")
                print(f"      Original entry: {t['original_entry']:.5f} ({t['original_volume']:.2f} lots)")
                print(f"      Hedge entry:    {t['hedge_entry']:.5f} ({t['hedge_volume']:.2f} lots)")
                print(f"      Time gap:       {t['time_before_hedge_minutes']:.1f} minutes")
                print(f"      Price movement: {t['price_movement_pips']:.1f} pips ({t['price_movement_pct']:.2f}%)")
                print(f"      Volume ratio:   {t['volume_multiplier']:.2f}x")

                if t['original_exit']:
                    print(f"      Original P&L:   ${t['original_profit']:.2f}")
                    print(f"      Hedge P&L:      ${t['hedge_profit']:.2f}")
                    print(f"      Net result:     ${t['net_result']:.2f}")

        print()
    else:
        print("⚠️ NO HEDGING DETECTED")
        print("  EA does not use opposite direction positions for hedging")
        print()

    # Recovery Sequences Analysis
    if recovery_analysis['recovery_sequences']:
        print("💊 CAPITAL RECOVERY MECHANISMS DETECTED!")
        print(f"  Total recovery sequences: {len(recovery_analysis['recovery_sequences'])}")
        print(f"  Maximum consecutive recovery attempts: {recovery_analysis['max_recovery_attempts']}")
        print(f"  Average lot multiplier: {recovery_analysis['avg_recovery_lot_multiplier']:.2f}x")
        print()

        if recovery_analysis['martingale_detected']:
            martingale_seqs = [s for s in recovery_analysis['recovery_sequences'] if s['is_martingale']]
            print("  🎲 MARTINGALE DETECTED!")
            print(f"    {len(martingale_seqs)} martingale sequences found")
            avg_multiplier = sum(s['avg_volume_multiplier'] for s in martingale_seqs) / len(martingale_seqs)
            avg_deterioration = sum(s['price_deterioration'] for s in martingale_seqs) / len(martingale_seqs)
            print(f"    Average lot multiplier: {avg_multiplier:.2f}x per step")
            print(f"    Average price deterioration: {avg_deterioration:.2f}%")
            print(f"    Longest sequence: {max(s['sequence_length'] for s in martingale_seqs)} trades")
            print()

        if recovery_analysis['dca_detected']:
            dca_seqs = [s for s in recovery_analysis['recovery_sequences'] if s['is_dca']]
            print("  📉 DCA (Dollar Cost Averaging) DETECTED!")
            print(f"    {len(dca_seqs)} DCA sequences found")
            avg_deterioration = sum(s['price_deterioration'] for s in dca_seqs) / len(dca_seqs)
            print(f"    Fixed lot size (no multiplier)")
            print(f"    Average price deterioration before recovery: {avg_deterioration:.2f}%")
            print(f"    Longest sequence: {max(s['sequence_length'] for s in dca_seqs)} trades")
            print()

        # Show detailed recovery examples
        print("  📋 Recovery Sequence Examples:")
        for idx, seq in enumerate(recovery_analysis['recovery_sequences'][:5], 1):
            recovery_type = "MARTINGALE" if seq['is_martingale'] else "DCA" if seq['is_dca'] else "GRID"
            print(f"    {idx}. {recovery_type} - {seq['trade_type'].upper()}")
            print(f"       Length: {seq['sequence_length']} trades")
            print(f"       Lot multiplier: {seq['avg_volume_multiplier']:.2f}x")
            print(f"       Price deterioration: {seq['price_deterioration']:.2f}%")
        print()

        # DETAILED RECOVERY SEQUENCE PLAYBACK
        print("  🎬 DETAILED RECOVERY SEQUENCE PLAYBACK:")
        print("  " + "="*70)
        print()

        # Find a good recovery sequence to show in detail
        if recovery_analysis['recovery_sequences']:
            # Get trades sorted by time
            trades_sorted = trades_df.sort_values('entry_time')

            # Track sequences in detail
            sequence_playbacks = []
            for symbol in trades_df['symbol'].unique():
                symbol_trades = trades_sorted[trades_sorted['symbol'] == symbol].copy()
                current_seq_trades = []

                for idx, trade in symbol_trades.iterrows():
                    if not current_seq_trades:
                        current_seq_trades.append(trade)
                    else:
                        prev_trade = current_seq_trades[-1]
                        time_diff = (pd.to_datetime(trade.get('entry_time')) -
                                   pd.to_datetime(prev_trade.get('entry_time'))).total_seconds() / 3600

                        if trade.get('trade_type') == prev_trade.get('trade_type') and time_diff < 1:
                            current_seq_trades.append(trade)
                        else:
                            if len(current_seq_trades) >= 2:
                                # Save this sequence
                                sequence_playbacks.append(current_seq_trades)
                            current_seq_trades = [trade]

                # Check last sequence
                if len(current_seq_trades) >= 2:
                    sequence_playbacks.append(current_seq_trades)

            # Show first detailed sequence
            if sequence_playbacks:
                seq = sequence_playbacks[0]
                print(f"  Example: {len(seq)}-trade {seq[0].get('trade_type', 'unknown').upper()} sequence")
                print()

                cumulative_lots = 0
                cumulative_cost = 0
                avg_entry = 0

                for i, trade in enumerate(seq, 1):
                    entry_price = trade.get('entry_price', 0)
                    volume = trade.get('volume', 0)
                    entry_time = pd.to_datetime(trade.get('entry_time'))
                    exit_price = trade.get('exit_price')
                    profit = trade.get('profit')

                    cumulative_lots += volume
                    cumulative_cost += entry_price * volume

                    if cumulative_lots > 0:
                        avg_entry = cumulative_cost / cumulative_lots

                    time_str = entry_time.strftime("%Y-%m-%d %H:%M") if not pd.isna(entry_time) else "N/A"

                    print(f"  Step {i}:")
                    print(f"    Entry: {entry_price:.5f} @ {time_str}")
                    print(f"    Volume: {volume:.2f} lots")

                    if i > 1:
                        prev_price = seq[i-2].get('entry_price', 0)
                        if prev_price > 0:
                            price_move = ((entry_price - prev_price) / prev_price * 100)
                            print(f"    Price moved: {price_move:+.2f}% since previous entry")

                        prev_volume = seq[i-2].get('volume', 0)
                        if prev_volume > 0:
                            vol_mult = volume / prev_volume
                            print(f"    Volume multiplier: {vol_mult:.2f}x")

                    print(f"    Cumulative position: {cumulative_lots:.2f} lots @ avg {avg_entry:.5f}")

                    if exit_price:
                        if seq[0].get('trade_type') == 'buy':
                            breakeven_pips = (avg_entry - entry_price) * 10000
                        else:
                            breakeven_pips = (entry_price - avg_entry) * 10000
                        print(f"    Breakeven distance: {breakeven_pips:.1f} pips from current")

                    if profit is not None:
                        print(f"    Result: ${profit:+.2f}")

                    print()

                # Calculate overall sequence result
                total_profit = sum(t.get('profit', 0) or 0 for t in seq)
                print(f"  Sequence Total P&L: ${total_profit:+.2f}")
                print()

        print()

        # Risk assessment
        print("  ⚠️ RISK ASSESSMENT:")
        if recovery_analysis['martingale_detected']:
            if recovery_analysis['avg_recovery_lot_multiplier'] > 2.0:
                print(f"    🔴 HIGH RISK: Aggressive martingale ({recovery_analysis['avg_recovery_lot_multiplier']:.1f}x multiplier)")
            else:
                print(f"    🟡 MODERATE RISK: Conservative martingale ({recovery_analysis['avg_recovery_lot_multiplier']:.1f}x multiplier)")

        if recovery_analysis['max_recovery_attempts'] > 5:
            print(f"    🔴 HIGH RISK: Up to {recovery_analysis['max_recovery_attempts']} consecutive recovery attempts")
        elif recovery_analysis['max_recovery_attempts'] > 3:
            print(f"    🟡 MODERATE RISK: Up to {recovery_analysis['max_recovery_attempts']} consecutive recovery attempts")

        max_deterioration = max(s['price_deterioration'] for s in recovery_analysis['recovery_sequences'])
        if max_deterioration > 2.0:
            print(f"    🔴 HIGH RISK: Adds to losing positions even at {max_deterioration:.1f}% loss")
        elif max_deterioration > 1.0:
            print(f"    🟡 MODERATE RISK: Adds to losing positions up to {max_deterioration:.1f}% loss")

    else:
        print("✅ NO AGGRESSIVE CAPITAL RECOVERY DETECTED")
        print("  EA does not use martingale or aggressive DCA strategies")
        print()

    # Position management
    print("\n" + "="*80)
    print("POSITION MANAGEMENT RULES")
    print("="*80 + "\n")

    mgmt = analyze_position_management(trades_df)

    if mgmt['grid_spacing']:
        print(f"📐 GRID TRADING DETECTED:")
        print(f"  Spacing: {mgmt['grid_spacing']:.5f} ({mgmt['grid_spacing'] * 10000:.1f} pips)")
        print(f"  Max simultaneous positions: {mgmt['max_positions']}")

    if mgmt['lot_progression']:
        print(f"\n📊 LOT SIZING:")
        print(f"  {mgmt['lot_progression']}")

    # Export detailed CSV
    if all_conditions:
        export_df = pd.DataFrame(all_conditions)
        export_df.to_csv('ea_reverse_engineering_detailed.csv', index=False)
        print(f"\n✅ Exported detailed analysis to: ea_reverse_engineering_detailed.csv")

    # TREND AVOIDANCE ANALYSIS
    print("\n" + "="*80)
    print("📈 TREND DETECTION ANALYSIS - DOES EA AVOID TRENDING MARKETS?")
    print("="*80 + "\n")

    if trades_with_trend_info:
        trend_df = pd.DataFrame(trades_with_trend_info)

        # Overall statistics
        total_analyzed = len(trend_df)
        strong_trend_trades = trend_df[trend_df['strong_trend'] == True]
        ranging_trades = trend_df[trend_df['strong_trend'] == False]

        print(f"📊 MARKET CONDITIONS WHEN EA TRADED:")
        print(f"  Total trades analyzed: {total_analyzed}")
        print(f"  Trades during STRONG TRENDS: {len(strong_trend_trades)} ({len(strong_trend_trades)/total_analyzed*100:.1f}%)")
        print(f"  Trades during RANGING markets: {len(ranging_trades)} ({len(ranging_trades)/total_analyzed*100:.1f}%)")
        print()

        # Trend direction breakdown
        uptrend_trades = trend_df[trend_df['trend_direction'] == 'uptrend']
        downtrend_trades = trend_df[trend_df['trend_direction'] == 'downtrend']
        neutral_trades = trend_df[trend_df['trend_direction'] == 'neutral']

        print(f"📊 TREND DIRECTION BREAKDOWN:")
        print(f"  Uptrend: {len(uptrend_trades)} trades ({len(uptrend_trades)/total_analyzed*100:.1f}%)")
        print(f"  Downtrend: {len(downtrend_trades)} trades ({len(downtrend_trades)/total_analyzed*100:.1f}%)")
        print(f"  Neutral/Ranging: {len(neutral_trades)} trades ({len(neutral_trades)/total_analyzed*100:.1f}%)")
        print()

        # Average trend strength at entry
        avg_trend_strength = trend_df['trend_strength'].mean()
        print(f"📊 AVERAGE TREND STRENGTH AT ENTRY: {avg_trend_strength:.2f}%")
        print(f"  (>1.0% = strong trend, <1.0% = ranging)")
        print()

        # Verdict
        strong_trend_pct = len(strong_trend_trades) / total_analyzed * 100

        print("💡 VERDICT:")
        if strong_trend_pct > 50:
            print(f"  ⚠️ EA DOES NOT AVOID TRENDS!")
            print(f"  {strong_trend_pct:.1f}% of trades happen during strong trends")
            print(f"  ⚠️ RISK: EA may add to losing positions against the trend")
        elif strong_trend_pct > 30:
            print(f"  🟡 EA TRADES IN MIXED CONDITIONS")
            print(f"  {strong_trend_pct:.1f}% during strong trends, {100-strong_trend_pct:.1f}% during ranging")
            print(f"  Moderately trend-aware")
        else:
            print(f"  ✅ EA PREFERS RANGING MARKETS!")
            print(f"  Only {strong_trend_pct:.1f}% of trades during strong trends")
            print(f"  ✅ GOOD: EA avoids trending conditions")

        # Trade type vs trend analysis
        if len(strong_trend_trades) > 0:
            buy_in_uptrend = strong_trend_trades[(strong_trend_trades['trade_type'] == 'buy') &
                                                 (strong_trend_trades['trend_direction'] == 'uptrend')]
            sell_in_downtrend = strong_trend_trades[(strong_trend_trades['trade_type'] == 'sell') &
                                                   (strong_trend_trades['trend_direction'] == 'downtrend')]
            counter_trend = len(strong_trend_trades) - len(buy_in_uptrend) - len(sell_in_downtrend)

            print()
            print(f"📊 TREND FOLLOWING vs COUNTER-TREND:")
            print(f"  With-trend trades: {len(buy_in_uptrend) + len(sell_in_downtrend)} ({(len(buy_in_uptrend) + len(sell_in_downtrend))/len(strong_trend_trades)*100:.1f}%)")
            print(f"  Counter-trend trades: {counter_trend} ({counter_trend/len(strong_trend_trades)*100:.1f}%)")

            if counter_trend > len(buy_in_uptrend) + len(sell_in_downtrend):
                print(f"  ⚠️ EA FIGHTS THE TREND - dangerous!")
            else:
                print(f"  ✅ EA generally follows the trend when trading")

    # COMPREHENSIVE SUMMARY
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE EA STRATEGY SUMMARY")
    print("="*80 + "\n")

    print("🎯 PRIMARY ENTRY STRATEGY:")
    if vwap_stats and vwap_stats['band_1_2_percentage'] > 40:
        print(f"  ✅ VWAP Mean Reversion (Bands 1 & 2)")
        print(f"     {vwap_stats['band_1_2_percentage']:.1f}% of trades at VWAP bands")
        if vwap_stats['band_1_2_at_swing'] > vwap_stats['band_1_2_trades'] * 0.4:
            print(f"     Combined with swing levels for confluence")
    else:
        print(f"  Market structure and technical indicators")

    print()
    print("💰 RISK MANAGEMENT:")
    if recovery_analysis['hedge_detected']:
        print(f"  🔄 Hedging: YES ({recovery_analysis['hedge_pairs'] // 2} pairs)")
        hedge_ratios = [h['volume_ratio'] for h in recovery_analysis['hedge_timing']]
        avg_ratio = sum(hedge_ratios) / len(hedge_ratios) if hedge_ratios else 1.0
        if 0.9 < avg_ratio < 1.1:
            print(f"     Type: Balanced hedge (equal volumes)")
        else:
            print(f"     Type: Partial hedge ({avg_ratio:.1f}x ratio)")
    else:
        print(f"  🔄 Hedging: NO")

    if recovery_analysis['martingale_detected']:
        print(f"  🎲 Martingale: YES ({recovery_analysis['avg_recovery_lot_multiplier']:.1f}x multiplier)")
        if recovery_analysis['avg_recovery_lot_multiplier'] > 2.0:
            print(f"     ⚠️ High risk - aggressive recovery")
    else:
        print(f"  🎲 Martingale: NO")

    if recovery_analysis['dca_detected']:
        print(f"  📉 DCA: YES (fixed lot averaging)")
    else:
        print(f"  📉 DCA: NO")

    if mgmt['grid_spacing']:
        print(f"  📐 Grid: YES ({mgmt['grid_spacing'] * 10000:.1f} pips spacing)")
    else:
        print(f"  📐 Grid: NO")

    print()
    print("🎲 OVERALL RISK PROFILE:")

    risk_score = 0
    risk_factors = []

    if recovery_analysis['martingale_detected'] and recovery_analysis['avg_recovery_lot_multiplier'] > 2.0:
        risk_score += 3
        risk_factors.append("Aggressive martingale")
    elif recovery_analysis['martingale_detected']:
        risk_score += 2
        risk_factors.append("Conservative martingale")

    if recovery_analysis['max_recovery_attempts'] > 5:
        risk_score += 2
        risk_factors.append(f"Deep recovery sequences ({recovery_analysis['max_recovery_attempts']} max)")
    elif recovery_analysis['max_recovery_attempts'] > 3:
        risk_score += 1
        risk_factors.append(f"Moderate recovery depth ({recovery_analysis['max_recovery_attempts']} max)")

    if recovery_analysis['hedge_detected']:
        risk_score -= 1  # Hedging reduces risk
        risk_factors.append("Hedging used (reduces risk)")

    if vwap_stats and vwap_stats['band_1_2_percentage'] > 40:
        risk_score -= 1  # Mean reversion at institutional levels
        risk_factors.append("Mean reversion at institutional levels")

    if risk_score >= 4:
        print(f"  🔴 HIGH RISK EA")
    elif risk_score >= 2:
        print(f"  🟡 MODERATE RISK EA")
    else:
        print(f"  🟢 CONSERVATIVE EA")

    if risk_factors:
        print(f"\n  Risk factors:")
        for factor in risk_factors:
            print(f"    • {factor}")

    print()
    print("💡 RECOMMENDED ACTIONS:")
    if recovery_analysis['martingale_detected'] and recovery_analysis['avg_recovery_lot_multiplier'] > 2.0:
        print(f"  ⚠️ Consider reducing martingale multiplier")
        print(f"  ⚠️ Implement maximum recovery attempt limits")
    if recovery_analysis['max_recovery_attempts'] > 5:
        print(f"  ⚠️ Limit maximum consecutive recovery attempts to 3-5")
    if not recovery_analysis['hedge_detected'] and recovery_analysis['martingale_detected']:
        print(f"  💡 Consider adding hedging to reduce drawdown during recovery")
    if risk_score < 2 and not recovery_analysis['hedge_detected']:
        print(f"  ✅ EA appears conservative - can potentially increase risk for higher returns")

    print("\n" + "="*80)
    print("REVERSE ENGINEERING COMPLETE")
    print("="*80)

    bot.stop()


if __name__ == "__main__":
    main()
