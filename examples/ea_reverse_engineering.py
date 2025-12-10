"""
EA Comprehensive Reverse Engineering
Complete dynamic analysis of EA behavior including:
- Entry strategy identification (VWAP bands, market structure)
- Capital recovery mechanisms (martingale, DCA, hedging)
- Risk assessment and recommendations
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot import MT5TradingBot
from src.utils import load_config, load_credentials, setup_logging
from src.ea_mining import EAMonitor, EAAnalyzer

# Import comprehensive analysis functions
from reverse_engineer_ea import (
    analyze_trade_entry_conditions,
    find_trade_patterns,
    analyze_vwap_mean_reversion,
    analyze_hedging_and_recovery,
    analyze_position_management
)


def main():
    print("\n" + "=" * 80)
    print("  EA COMPREHENSIVE REVERSE ENGINEERING")
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

    # ===================================================================
    # STEP 1: Monitor EA and Get Basic Statistics
    # ===================================================================
    print("=" * 80)
    print("STEP 1: EA Monitoring & Statistics")
    print("=" * 80 + "\n")

    ea_monitor = EAMonitor(bot.mt5_manager, bot.storage)
    ea_monitor.start_monitoring()

    ea_stats = ea_monitor.get_ea_statistics()

    print(f"EA Statistics:")
    print(f"  Total Trades:    {ea_stats.get('total_trades', 0)}")
    print(f"  Open Trades:     {ea_stats.get('open_trades', 0)}")
    print(f"  Win Rate:        {ea_stats.get('win_rate', 0):.1f}%")
    print(f"  Total Profit:    ${ea_stats.get('total_profit', 0):.2f}")
    print(f"  Average Win:     ${ea_stats.get('average_win', 0):.2f}")
    print(f"  Average Loss:    ${ea_stats.get('average_loss', 0):.2f}")
    print(f"  Profit Factor:   {ea_stats.get('profit_factor', 0):.2f}")

    if ea_stats.get('total_trades', 0) == 0:
        print("\n⚠️  No trades found!")
        print("   Make sure your EA has made some trades.")
        bot.stop()
        return

    # ===================================================================
    # STEP 2: Load Market Data for Analysis
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 2: Loading Market Data")
    print("=" * 80 + "\n")

    trades_df = ea_monitor.get_trades_dataframe()
    symbols = list(set(trade.symbol for trade in ea_monitor.known_trades.values()))
    symbol = symbols[0] if symbols else 'EURUSD'

    print(f"Fetching market data for {symbol}...")
    market_data = bot.collector.get_latest_data(symbol, 'H1', bars=5000)

    if market_data is None or market_data.empty:
        print("❌ Failed to fetch market data")
        bot.stop()
        return

    market_data = bot.indicator_manager.calculate_all(market_data)
    print(f"✅ Loaded {len(market_data)} bars with indicators\n")

    # ===================================================================
    # STEP 3: Analyze Trade Entry Conditions
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 3: Trade-by-Trade Market Structure Analysis")
    print("=" * 80 + "\n")

    print(f"Analyzing {len(trades_df)} trades...")
    all_conditions = []

    for idx, trade in trades_df.iterrows():
        conditions = analyze_trade_entry_conditions(trade, market_data, market_data)
        if conditions:
            all_conditions.append(conditions)

    print(f"✅ Analyzed {len(all_conditions)} trades with complete market structure\n")

    # ===================================================================
    # STEP 4: Deduce Entry Rules
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 4: Deduced Entry Rules")
    print("=" * 80 + "\n")

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

    # ===================================================================
    # STEP 5: VWAP Mean Reversion Analysis (Bands 1 & 2 Focus)
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 5: 🎯 VWAP MEAN REVERSION ANALYSIS (BANDS 1 & 2 FOCUS)")
    print("=" * 80 + "\n")

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

            print("🎯 CONFLUENCE WITH OTHER MARKET STRUCTURE:")
            if vwap_stats['band_1_2_at_swing'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_swing'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Swing Highs/Lows: {vwap_stats['band_1_2_at_swing']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_at_order_blocks'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_order_blocks'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Order Blocks: {vwap_stats['band_1_2_at_order_blocks']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_at_poc'] > 0:
                confluence_pct = vwap_stats['band_1_2_at_poc'] / vwap_stats['band_1_2_trades'] * 100
                print(f"  + Volume Profile POC: {vwap_stats['band_1_2_at_poc']} ({confluence_pct:.0f}%)")
            if vwap_stats['band_1_2_outside_value_area'] > 0:
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

    # ===================================================================
    # STEP 6: Capital Recovery & Hedging Analysis
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 6: 💰 CAPITAL RECOVERY & HEDGING MECHANISMS")
    print("=" * 80 + "\n")

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

            print("\n  📋 Hedge Examples:")
            for idx, hedge in enumerate(recovery_analysis['hedge_timing'][:3], 1):
                print(f"    {idx}. {hedge['original_type'].upper()} → {hedge['hedge_type'].upper()}")
                print(f"       Time gap: {abs(hedge['time_diff']):.1f} min, Volume ratio: {hedge['volume_ratio']:.2f}x")
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

        print("  📋 Recovery Sequence Examples:")
        for idx, seq in enumerate(recovery_analysis['recovery_sequences'][:5], 1):
            recovery_type = "MARTINGALE" if seq['is_martingale'] else "DCA" if seq['is_dca'] else "GRID"
            print(f"    {idx}. {recovery_type} - {seq['trade_type'].upper()}")
            print(f"       Length: {seq['sequence_length']} trades")
            print(f"       Lot multiplier: {seq['avg_volume_multiplier']:.2f}x")
            print(f"       Price deterioration: {seq['price_deterioration']:.2f}%")
        print()

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

    # ===================================================================
    # STEP 7: Position Management
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 7: Position Management Rules")
    print("=" * 80 + "\n")

    mgmt = analyze_position_management(trades_df)

    if mgmt['grid_spacing']:
        print(f"📐 GRID TRADING DETECTED:")
        print(f"  Spacing: {mgmt['grid_spacing']:.5f} ({mgmt['grid_spacing'] * 10000:.1f} pips)")
        print(f"  Max simultaneous positions: {mgmt['max_positions']}")

    if mgmt['lot_progression']:
        print(f"\n📊 LOT SIZING:")
        print(f"  {mgmt['lot_progression']}")

    # ===================================================================
    # STEP 8: Comprehensive Summary
    # ===================================================================
    print("\n" + "=" * 80)
    print("STEP 8: 📊 COMPREHENSIVE EA STRATEGY SUMMARY")
    print("=" * 80 + "\n")

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
        risk_score -= 1
        risk_factors.append("Hedging used (reduces risk)")

    if vwap_stats and vwap_stats['band_1_2_percentage'] > 40:
        risk_score -= 1
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

    # Export CSV
    if all_conditions:
        export_df = pd.DataFrame(all_conditions)
        export_df.to_csv('ea_reverse_engineering_detailed.csv', index=False)
        print(f"\n✅ Exported detailed analysis to: ea_reverse_engineering_detailed.csv")

    print("\n" + "=" * 80)
    print("REVERSE ENGINEERING COMPLETE")
    print("=" * 80)

    bot.stop()


if __name__ == "__main__":
    main()
