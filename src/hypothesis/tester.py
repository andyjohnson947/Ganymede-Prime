"""
Hypothesis Testing Framework
Statistical validation of trading signals and patterns
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from scipy import stats
from datetime import datetime


@dataclass
class TestResult:
    """Container for hypothesis test results"""
    test_name: str
    test_type: str
    test_date: datetime
    p_value: float
    statistic: float
    result: str  # 'reject_null' or 'fail_to_reject'
    confidence_level: float
    sample_size: int
    metadata: Dict


class HypothesisTester:
    """Performs statistical hypothesis tests on trading data"""

    def __init__(self, significance_level: float = 0.05, min_sample_size: int = 30):
        """
        Initialize Hypothesis Tester

        Args:
            significance_level: Alpha level for tests (default 0.05)
            min_sample_size: Minimum sample size required
        """
        self.significance_level = significance_level
        self.min_sample_size = min_sample_size
        self.logger = logging.getLogger(__name__)

    def test_pattern_profitability(
        self,
        pattern_signals: pd.DataFrame,
        returns: pd.Series
    ) -> TestResult:
        """
        Test if pattern signals lead to statistically significant returns

        Args:
            pattern_signals: DataFrame with pattern detection times
            returns: Series of returns indexed by time

        Returns:
            TestResult object
        """
        self.logger.info("Testing pattern profitability")

        # Get returns following pattern signals
        signal_returns = []
        for signal_time in pattern_signals.index:
            # Get next return after signal
            future_returns = returns[returns.index > signal_time]
            if len(future_returns) > 0:
                signal_returns.append(future_returns.iloc[0])

        if len(signal_returns) < self.min_sample_size:
            self.logger.warning(f"Insufficient sample size: {len(signal_returns)}")
            return TestResult(
                test_name="Pattern Profitability",
                test_type="t_test",
                test_date=datetime.now(),
                p_value=1.0,
                statistic=0.0,
                result="insufficient_data",
                confidence_level=1 - self.significance_level,
                sample_size=len(signal_returns),
                metadata={'error': 'Sample size too small'}
            )

        # One-sample t-test: Are returns significantly different from 0?
        statistic, p_value = stats.ttest_1samp(signal_returns, 0)

        result = "reject_null" if p_value < self.significance_level else "fail_to_reject"

        return TestResult(
            test_name="Pattern Profitability",
            test_type="t_test",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=statistic,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(signal_returns),
            metadata={
                'mean_return': np.mean(signal_returns),
                'std_return': np.std(signal_returns),
                'interpretation': 'Pattern signals lead to significant returns' if result == 'reject_null'
                                 else 'No significant evidence of pattern profitability'
            }
        )

    def test_indicator_effectiveness(
        self,
        indicator_values: pd.Series,
        future_returns: pd.Series,
        threshold: float = 0
    ) -> TestResult:
        """
        Test if indicator values predict future returns

        Args:
            indicator_values: Series of indicator values
            future_returns: Series of future returns (aligned with indicator)
            threshold: Threshold to separate high/low indicator values

        Returns:
            TestResult object
        """
        self.logger.info("Testing indicator effectiveness")

        # Align data
        aligned_df = pd.DataFrame({
            'indicator': indicator_values,
            'returns': future_returns
        }).dropna()

        if len(aligned_df) < self.min_sample_size:
            self.logger.warning("Insufficient sample size")
            return self._insufficient_data_result("Indicator Effectiveness", len(aligned_df))

        # Split returns by indicator threshold
        high_indicator = aligned_df[aligned_df['indicator'] > threshold]['returns']
        low_indicator = aligned_df[aligned_df['indicator'] <= threshold]['returns']

        if len(high_indicator) < 2 or len(low_indicator) < 2:
            return self._insufficient_data_result("Indicator Effectiveness", len(aligned_df))

        # Mann-Whitney U test: Do high and low indicator values lead to different returns?
        statistic, p_value = stats.mannwhitneyu(high_indicator, low_indicator, alternative='two-sided')

        result = "reject_null" if p_value < self.significance_level else "fail_to_reject"

        return TestResult(
            test_name="Indicator Effectiveness",
            test_type="mann_whitney",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=statistic,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(aligned_df),
            metadata={
                'mean_return_high': high_indicator.mean(),
                'mean_return_low': low_indicator.mean(),
                'high_sample_size': len(high_indicator),
                'low_sample_size': len(low_indicator),
                'interpretation': 'Indicator has significant predictive power' if result == 'reject_null'
                                 else 'No significant evidence of indicator effectiveness'
            }
        )

    def test_strategy_vs_benchmark(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> TestResult:
        """
        Test if strategy returns are significantly different from benchmark

        Args:
            strategy_returns: Series of strategy returns
            benchmark_returns: Series of benchmark returns (e.g., buy-and-hold)

        Returns:
            TestResult object
        """
        self.logger.info("Testing strategy vs benchmark")

        # Align returns
        aligned_df = pd.DataFrame({
            'strategy': strategy_returns,
            'benchmark': benchmark_returns
        }).dropna()

        if len(aligned_df) < self.min_sample_size:
            return self._insufficient_data_result("Strategy vs Benchmark", len(aligned_df))

        # Paired t-test
        statistic, p_value = stats.ttest_rel(aligned_df['strategy'], aligned_df['benchmark'])

        result = "reject_null" if p_value < self.significance_level else "fail_to_reject"

        return TestResult(
            test_name="Strategy vs Benchmark",
            test_type="paired_t_test",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=statistic,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(aligned_df),
            metadata={
                'mean_strategy': aligned_df['strategy'].mean(),
                'mean_benchmark': aligned_df['benchmark'].mean(),
                'mean_difference': (aligned_df['strategy'] - aligned_df['benchmark']).mean(),
                'interpretation': 'Strategy significantly outperforms benchmark' if result == 'reject_null' and statistic > 0
                                 else 'Strategy significantly underperforms benchmark' if result == 'reject_null'
                                 else 'No significant difference from benchmark'
            }
        )

    def test_returns_normality(self, returns: pd.Series) -> TestResult:
        """
        Test if returns follow a normal distribution

        Args:
            returns: Series of returns

        Returns:
            TestResult object
        """
        self.logger.info("Testing returns normality")

        returns_clean = returns.dropna()

        if len(returns_clean) < self.min_sample_size:
            return self._insufficient_data_result("Returns Normality", len(returns_clean))

        # Kolmogorov-Smirnov test for normality
        statistic, p_value = stats.kstest(returns_clean, 'norm',
                                          args=(returns_clean.mean(), returns_clean.std()))

        result = "reject_null" if p_value < self.significance_level else "fail_to_reject"

        return TestResult(
            test_name="Returns Normality",
            test_type="kolmogorov_smirnov",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=statistic,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(returns_clean),
            metadata={
                'mean': returns_clean.mean(),
                'std': returns_clean.std(),
                'skewness': stats.skew(returns_clean),
                'kurtosis': stats.kurtosis(returns_clean),
                'interpretation': 'Returns do not follow normal distribution' if result == 'reject_null'
                                 else 'Returns appear normally distributed'
            }
        )

    def test_mean_reversion(
        self,
        prices: pd.Series,
        window: int = 20
    ) -> TestResult:
        """
        Test if price series exhibits mean reversion

        Args:
            prices: Series of prices
            window: Rolling window for mean calculation

        Returns:
            TestResult object
        """
        self.logger.info("Testing mean reversion")

        prices_clean = prices.dropna()

        if len(prices_clean) < self.min_sample_size + window:
            return self._insufficient_data_result("Mean Reversion", len(prices_clean))

        # Calculate deviations from rolling mean
        rolling_mean = prices_clean.rolling(window=window).mean()
        deviations = prices_clean - rolling_mean
        deviations = deviations.dropna()

        # Calculate autocorrelation at lag 1
        # Negative autocorrelation suggests mean reversion
        lag1_corr = deviations.autocorr(lag=1)

        # Use t-test to check if correlation is significantly negative
        n = len(deviations)
        t_stat = lag1_corr * np.sqrt((n - 2) / (1 - lag1_corr**2))
        p_value = stats.t.cdf(t_stat, n - 2)  # One-tailed test for negative correlation

        result = "reject_null" if p_value < self.significance_level and lag1_corr < 0 else "fail_to_reject"

        return TestResult(
            test_name="Mean Reversion",
            test_type="autocorrelation",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=lag1_corr,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(deviations),
            metadata={
                'lag1_correlation': lag1_corr,
                'window': window,
                'interpretation': 'Significant mean reversion detected' if result == 'reject_null'
                                 else 'No significant mean reversion'
            }
        )

    def test_momentum(
        self,
        returns: pd.Series,
        lookback: int = 20
    ) -> TestResult:
        """
        Test if there is significant momentum in returns

        Args:
            returns: Series of returns
            lookback: Lookback period for momentum

        Returns:
            TestResult object
        """
        self.logger.info("Testing momentum")

        returns_clean = returns.dropna()

        if len(returns_clean) < self.min_sample_size + lookback:
            return self._insufficient_data_result("Momentum", len(returns_clean))

        # Calculate momentum: correlation between past and future returns
        past_returns = returns_clean.rolling(window=lookback).sum().shift(1)
        future_returns = returns_clean.shift(-1)

        aligned_df = pd.DataFrame({
            'past': past_returns,
            'future': future_returns
        }).dropna()

        if len(aligned_df) < self.min_sample_size:
            return self._insufficient_data_result("Momentum", len(aligned_df))

        # Correlation test
        corr, p_value = stats.pearsonr(aligned_df['past'], aligned_df['future'])

        result = "reject_null" if p_value < self.significance_level else "fail_to_reject"

        return TestResult(
            test_name="Momentum",
            test_type="correlation",
            test_date=datetime.now(),
            p_value=p_value,
            statistic=corr,
            result=result,
            confidence_level=1 - self.significance_level,
            sample_size=len(aligned_df),
            metadata={
                'correlation': corr,
                'lookback': lookback,
                'interpretation': 'Significant momentum detected' if result == 'reject_null' and corr > 0
                                 else 'Significant reversal tendency' if result == 'reject_null'
                                 else 'No significant momentum'
            }
        )

    def run_comprehensive_tests(
        self,
        df: pd.DataFrame,
        returns_col: str = 'returns'
    ) -> List[TestResult]:
        """
        Run a comprehensive suite of hypothesis tests

        Args:
            df: DataFrame with price/returns data
            returns_col: Name of returns column

        Returns:
            List of TestResult objects
        """
        self.logger.info("Running comprehensive hypothesis tests")

        results = []

        # Test returns normality
        if returns_col in df.columns:
            results.append(self.test_returns_normality(df[returns_col]))

        # Test mean reversion
        if 'close' in df.columns:
            results.append(self.test_mean_reversion(df['close']))

        # Test momentum
        if returns_col in df.columns:
            results.append(self.test_momentum(df[returns_col]))

        self.logger.info(f"Completed {len(results)} hypothesis tests")
        return results

    def _insufficient_data_result(self, test_name: str, sample_size: int) -> TestResult:
        """Helper to create result for insufficient data"""
        return TestResult(
            test_name=test_name,
            test_type="insufficient_data",
            test_date=datetime.now(),
            p_value=1.0,
            statistic=0.0,
            result="insufficient_data",
            confidence_level=1 - self.significance_level,
            sample_size=sample_size,
            metadata={'error': f'Sample size {sample_size} < minimum {self.min_sample_size}'}
        )
