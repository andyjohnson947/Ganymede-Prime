"""
EA Learner
Machine learning model that learns from the EA's trading decisions
Uses imitation learning to replicate and improve upon EA behavior
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, List
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from .ea_monitor import EAMonitor
from ..ml import FeatureEngineer


class EALearner:
    """Learns the EA's trading strategy using machine learning"""

    def __init__(self, ea_monitor: EAMonitor, feature_engineer: FeatureEngineer):
        """
        Initialize EA Learner

        Args:
            ea_monitor: EA monitor with collected trades
            feature_engineer: Feature engineer for creating ML features
        """
        self.monitor = ea_monitor
        self.feature_engineer = feature_engineer
        self.logger = logging.getLogger(__name__)

        # Models
        self.entry_model = None  # Learns when EA enters
        self.direction_model = None  # Learns buy vs sell decision
        self.exit_model = None  # Learns when EA exits

        self.feature_names = []

    def prepare_training_data(
        self,
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Prepare training data by matching EA trades with market conditions

        Args:
            price_data: Dictionary of {symbol: DataFrame} with price/indicator data

        Returns:
            Tuple of (entry_data, direction_data, exit_data)
        """
        self.logger.info("Preparing training data from EA trades...")

        trades_df = self.monitor.get_trades_dataframe()

        if trades_df.empty:
            self.logger.error("No trades available for training")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        entry_samples = []
        direction_samples = []
        exit_samples = []

        for _, trade in trades_df.iterrows():
            symbol = trade['symbol']

            if symbol not in price_data:
                continue

            df = price_data[symbol]

            # Find the bar where EA entered
            entry_time = pd.to_datetime(trade['entry_time'])

            # Get closest bar
            if entry_time not in df.index:
                # Find nearest time
                nearest_idx = df.index.get_indexer([entry_time], method='nearest')[0]
                if nearest_idx >= 0:
                    entry_time = df.index[nearest_idx]
                else:
                    continue

            # Get data up to entry point
            entry_idx = df.index.get_loc(entry_time)

            if entry_idx < 100:  # Need enough history
                continue

            # Extract features at entry
            entry_features = df.iloc[entry_idx].to_dict()
            entry_features['symbol'] = symbol

            # Label: EA decided to trade
            entry_features['ea_traded'] = 1
            entry_samples.append(entry_features)

            # For direction model
            direction_features = entry_features.copy()
            direction_features['direction'] = 1 if trade['type'] == 'buy' else 0
            direction_samples.append(direction_features)

            # For exit model (if trade is closed)
            if pd.notna(trade['exit_time']):
                exit_time = pd.to_datetime(trade['exit_time'])

                # Find exit bar
                if exit_time not in df.index:
                    nearest_idx = df.index.get_indexer([exit_time], method='nearest')[0]
                    if nearest_idx >= 0:
                        exit_time = df.index[nearest_idx]

                try:
                    exit_idx = df.index.get_loc(exit_time)

                    # Get bars between entry and exit
                    bars_between = df.iloc[entry_idx:exit_idx + 1]

                    for i, (bar_time, bar_data) in enumerate(bars_between.iterrows()):
                        exit_features = bar_data.to_dict()
                        exit_features['symbol'] = symbol
                        exit_features['bars_since_entry'] = i
                        exit_features['current_pnl'] = trade['profit'] if i == len(bars_between) - 1 else 0

                        # Label: EA exited on last bar
                        exit_features['ea_exited'] = 1 if i == len(bars_between) - 1 else 0
                        exit_samples.append(exit_features)

                except:
                    continue

        # Create non-trade samples (when EA didn't trade)
        # Sample random bars where EA didn't enter
        for symbol, df in price_data.items():
            # Engineer features
            df = self.feature_engineer.engineer_all_features(df)

            # Get trade times for this symbol
            symbol_trades = trades_df[trades_df['symbol'] == symbol]
            trade_times = pd.to_datetime(symbol_trades['entry_time']).values

            # Sample non-trade bars
            non_trade_samples = []
            for idx in range(100, len(df), 10):  # Sample every 10th bar
                bar_time = df.index[idx]

                # Check if this was a trade time
                if any(abs((bar_time - pd.Timestamp(t)).total_seconds()) < 3600 for t in trade_times):
                    continue  # Skip if within 1 hour of a trade

                non_trade_features = df.iloc[idx].to_dict()
                non_trade_features['symbol'] = symbol
                non_trade_features['ea_traded'] = 0  # EA did not trade
                non_trade_samples.append(non_trade_features)

            entry_samples.extend(non_trade_samples)

        entry_df = pd.DataFrame(entry_samples)
        direction_df = pd.DataFrame(direction_samples)
        exit_df = pd.DataFrame(exit_samples)

        self.logger.info(f"Prepared training data:")
        self.logger.info(f"  Entry samples: {len(entry_df)} ({(entry_df['ea_traded']==1).sum()} trades)")
        self.logger.info(f"  Direction samples: {len(direction_df)}")
        self.logger.info(f"  Exit samples: {len(exit_df)}")

        return entry_df, direction_df, exit_df

    def train(self, price_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Train models to learn EA's behavior

        Args:
            price_data: Dictionary of {symbol: DataFrame} with enriched price data

        Returns:
            Dictionary with training results
        """
        self.logger.info("Training EA imitation models...")

        # Prepare data
        entry_df, direction_df, exit_df = self.prepare_training_data(price_data)

        results = {}

        # Train entry model (when to trade)
        if not entry_df.empty:
            self.logger.info("Training entry timing model...")
            entry_results = self._train_entry_model(entry_df)
            results['entry_model'] = entry_results

        # Train direction model (buy vs sell)
        if not direction_df.empty:
            self.logger.info("Training direction model...")
            direction_results = self._train_direction_model(direction_df)
            results['direction_model'] = direction_results

        # Train exit model (when to close)
        if not exit_df.empty:
            self.logger.info("Training exit model...")
            exit_results = self._train_exit_model(exit_df)
            results['exit_model'] = exit_results

        self.logger.info("EA learning complete")
        return results

    def _train_entry_model(self, entry_df: pd.DataFrame) -> Dict:
        """Train model to predict when EA enters trades"""
        # Select features - exclude non-numeric and target columns
        exclude_cols = ['ea_traded', 'symbol', 'time', 'timeframe']
        feature_cols = [col for col in entry_df.columns
                       if col not in exclude_cols and entry_df[col].dtype in ['float64', 'int64', 'float32', 'int32']]

        X = entry_df[feature_cols].fillna(0)
        y = entry_df['ea_traded']

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Train model
        self.entry_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )

        self.entry_model.fit(X_train, y_train)
        self.entry_feature_names = list(feature_cols)

        # Evaluate
        y_pred = self.entry_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Feature importance
        feature_importance = dict(zip(feature_cols, self.entry_model.feature_importances_))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'accuracy': accuracy,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'top_features': dict(top_features)
        }

    def _train_direction_model(self, direction_df: pd.DataFrame) -> Dict:
        """Train model to predict trade direction (buy vs sell)"""
        exclude_cols = ['direction', 'symbol', 'time', 'ea_traded', 'timeframe']
        feature_cols = [col for col in direction_df.columns
                       if col not in exclude_cols and direction_df[col].dtype in ['float64', 'int64', 'float32', 'int32']]

        X = direction_df[feature_cols].fillna(0)
        y = direction_df['direction']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.direction_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )

        self.direction_model.fit(X_train, y_train)

        # Store feature names for direction model
        self.direction_feature_names = list(feature_cols)

        y_pred = self.direction_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        feature_importance = dict(zip(feature_cols, self.direction_model.feature_importances_))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'accuracy': accuracy,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'top_features': dict(top_features)
        }

    def _train_exit_model(self, exit_df: pd.DataFrame) -> Dict:
        """Train model to predict when to exit"""
        exclude_cols = ['ea_exited', 'symbol', 'time', 'timeframe']
        feature_cols = [col for col in exit_df.columns
                       if col not in exclude_cols and exit_df[col].dtype in ['float64', 'int64', 'float32', 'int32']]

        X = exit_df[feature_cols].fillna(0)
        y = exit_df['ea_exited']

        if len(X) < 50:
            return {'error': 'Insufficient exit samples'}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.exit_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )

        self.exit_model.fit(X_train, y_train)

        y_pred = self.exit_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        return {
            'accuracy': accuracy,
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }

    def predict(self, current_data: pd.DataFrame) -> Dict:
        """
        Predict what the EA would do given current market conditions

        Args:
            current_data: DataFrame with current market data and features

        Returns:
            Dictionary with predictions
        """
        if self.entry_model is None:
            return {'error': 'Models not trained'}

        # Get latest bar
        latest = current_data.iloc[[-1]]

        predictions = {}

        # Should EA trade? (use entry model features)
        if self.entry_model and hasattr(self, 'entry_feature_names'):
            # Select only features used in entry model training
            X_entry = latest[self.entry_feature_names].fillna(0).astype(float)

            should_trade_proba = self.entry_model.predict_proba(X_entry)[0]
            predictions['should_trade'] = bool(should_trade_proba[1] > 0.5)
            predictions['trade_probability'] = float(should_trade_proba[1])

        # Trade direction (use direction model features)
        if self.direction_model and predictions.get('should_trade') and hasattr(self, 'direction_feature_names'):
            # Select only features used in direction model training
            X_direction = latest[self.direction_feature_names].fillna(0).astype(float)

            direction_proba = self.direction_model.predict_proba(X_direction)[0]
            predictions['direction'] = 'buy' if direction_proba[1] > 0.5 else 'sell'
            predictions['direction_confidence'] = float(max(direction_proba))
        else:
            predictions['direction'] = None
            predictions['direction_confidence'] = 0.0

        return predictions

    def get_learned_strategy_summary(self) -> Dict:
        """
        Get a summary of what the model learned about the EA

        Returns:
            Dictionary with learned strategy insights
        """
        if self.entry_model is None:
            return {'error': 'Models not trained'}

        summary = {
            'top_entry_factors': [],
            'top_direction_factors': []
        }

        # Entry factors
        if self.entry_model:
            feature_importance = dict(zip(self.feature_names,
                                        self.entry_model.feature_importances_))
            top_entry = sorted(feature_importance.items(),
                             key=lambda x: x[1], reverse=True)[:10]

            summary['top_entry_factors'] = [
                {'feature': name, 'importance': float(imp)}
                for name, imp in top_entry
            ]

        # Direction factors
        if self.direction_model:
            feature_importance = dict(zip(self.feature_names,
                                        self.direction_model.feature_importances_))
            top_direction = sorted(feature_importance.items(),
                                 key=lambda x: x[1], reverse=True)[:10]

            summary['top_direction_factors'] = [
                {'feature': name, 'importance': float(imp)}
                for name, imp in top_direction
            ]

        return summary
