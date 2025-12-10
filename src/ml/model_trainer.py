"""
ML Model Trainer
Trains Random Forest and Gradient Boosting models
"""

import pandas as pd
import numpy as np
import logging
import pickle
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.preprocessing import StandardScaler

from .feature_engineer import FeatureEngineer


class MLModelTrainer:
    """Trains machine learning models for trading predictions"""

    def __init__(self, config: Dict):
        """
        Initialize ML Model Trainer

        Args:
            config: ML configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Feature engineer
        self.feature_engineer = FeatureEngineer(config)

        # Models
        self.random_forest = None
        self.gradient_boosting = None
        self.scaler = StandardScaler()

        # Model metadata
        self.feature_names: List[str] = []
        self.trained_at: Optional[datetime] = None
        self.model_type = config.get('model_type', 'random_forest')

        # Initialize models
        self._initialize_models()

    def _initialize_models(self):
        """Initialize ML models based on configuration"""
        # Random Forest
        rf_config = self.config.get('random_forest', {})
        self.random_forest = RandomForestClassifier(
            n_estimators=rf_config.get('n_estimators', 100),
            max_depth=rf_config.get('max_depth', 10),
            min_samples_split=rf_config.get('min_samples_split', 5),
            random_state=rf_config.get('random_state', 42),
            n_jobs=-1  # Use all CPU cores
        )

        # Gradient Boosting
        gb_config = self.config.get('gradient_boosting', {})
        self.gradient_boosting = GradientBoostingClassifier(
            n_estimators=gb_config.get('n_estimators', 100),
            learning_rate=gb_config.get('learning_rate', 0.1),
            max_depth=gb_config.get('max_depth', 5),
            random_state=gb_config.get('random_state', 42)
        )

        self.logger.info("ML models initialized")

    def prepare_data(
        self,
        df: pd.DataFrame,
        target_column: str = None
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare data for training

        Args:
            df: DataFrame with price data and indicators
            target_column: Name of target column (if already exists)

        Returns:
            Tuple of (features_df, target_series)
        """
        self.logger.info("Preparing data for training...")

        # Engineer features
        df = self.feature_engineer.engineer_all_features(df)

        # Create target if not provided
        if target_column is None or target_column not in df.columns:
            df = self._create_target(df)
            target_column = 'target'

        # Get feature columns
        feature_cols = self.feature_engineer.get_feature_names(df)

        # Remove target from features if present
        if target_column in feature_cols:
            feature_cols.remove(target_column)

        # Create feature and target dataframes
        X = df[feature_cols].copy()
        y = df[target_column].copy()

        # Remove rows with NaN
        mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[mask]
        y = y[mask]

        self.logger.info(f"Data prepared: {len(X)} samples, {len(feature_cols)} features")
        return X, y

    def _create_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create target variable (future price direction)

        Args:
            df: DataFrame with price data

        Returns:
            DataFrame with target column added
        """
        prediction_horizon = self.config.get('prediction_horizon', 5)

        # Calculate future returns
        df['future_returns'] = df['close'].pct_change(prediction_horizon).shift(-prediction_horizon)

        # Create binary target (1 = up, 0 = down)
        df['target'] = (df['future_returns'] > 0).astype(int)

        return df

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        validation_split: float = None
    ) -> Dict:
        """
        Train ML models

        Args:
            X: Feature dataframe
            y: Target series
            validation_split: Validation split ratio (uses config if None)

        Returns:
            Training results dictionary
        """
        self.logger.info("Starting model training...")

        # Store feature names
        self.feature_names = list(X.columns)

        # Split data
        if validation_split is None:
            validation_split = 1.0 - self.config.get('train_test_split', 0.8)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=validation_split,
            random_state=42,
            shuffle=False  # Don't shuffle time series data
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        results = {}

        # Train Random Forest
        if self.model_type in ['random_forest', 'both']:
            self.logger.info("Training Random Forest...")
            self.random_forest.fit(X_train_scaled, y_train)

            # Evaluate
            rf_results = self._evaluate_model(
                self.random_forest,
                X_train_scaled, y_train,
                X_test_scaled, y_test,
                "Random Forest"
            )
            results['random_forest'] = rf_results

        # Train Gradient Boosting
        if self.model_type in ['gradient_boosting', 'both']:
            self.logger.info("Training Gradient Boosting...")
            self.gradient_boosting.fit(X_train_scaled, y_train)

            # Evaluate
            gb_results = self._evaluate_model(
                self.gradient_boosting,
                X_train_scaled, y_train,
                X_test_scaled, y_test,
                "Gradient Boosting"
            )
            results['gradient_boosting'] = gb_results

        # Cross-validation
        cv_folds = self.config.get('cross_validation_folds', 5)
        if cv_folds > 1:
            results['cross_validation'] = self._perform_cross_validation(
                X_train_scaled, y_train, cv_folds
            )

        # Feature importance
        results['feature_importance'] = self._get_feature_importance()

        self.trained_at = datetime.now()
        results['trained_at'] = self.trained_at

        self.logger.info("Model training complete")
        return results

    def _evaluate_model(
        self,
        model,
        X_train, y_train,
        X_test, y_test,
        model_name: str
    ) -> Dict:
        """Evaluate model performance"""
        # Train predictions
        y_train_pred = model.predict(X_train)
        train_accuracy = accuracy_score(y_train, y_train_pred)

        # Test predictions
        y_test_pred = model.predict(X_test)
        test_accuracy = accuracy_score(y_test, y_test_pred)

        # Detailed metrics
        precision = precision_score(y_test, y_test_pred, zero_division=0)
        recall = recall_score(y_test, y_test_pred, zero_division=0)
        f1 = f1_score(y_test, y_test_pred, zero_division=0)

        self.logger.info(f"{model_name} - Train Accuracy: {train_accuracy:.4f}, "
                        f"Test Accuracy: {test_accuracy:.4f}")

        return {
            'model_name': model_name,
            'train_accuracy': train_accuracy,
            'test_accuracy': test_accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'train_samples': len(y_train),
            'test_samples': len(y_test)
        }

    def _perform_cross_validation(
        self,
        X: np.ndarray,
        y: pd.Series,
        cv_folds: int
    ) -> Dict:
        """Perform cross-validation"""
        self.logger.info(f"Performing {cv_folds}-fold cross-validation...")

        results = {}

        if self.model_type in ['random_forest', 'both']:
            rf_scores = cross_val_score(self.random_forest, X, y, cv=cv_folds)
            results['random_forest'] = {
                'scores': rf_scores.tolist(),
                'mean': rf_scores.mean(),
                'std': rf_scores.std()
            }
            self.logger.info(f"Random Forest CV: {rf_scores.mean():.4f} (+/- {rf_scores.std():.4f})")

        if self.model_type in ['gradient_boosting', 'both']:
            gb_scores = cross_val_score(self.gradient_boosting, X, y, cv=cv_folds)
            results['gradient_boosting'] = {
                'scores': gb_scores.tolist(),
                'mean': gb_scores.mean(),
                'std': gb_scores.std()
            }
            self.logger.info(f"Gradient Boosting CV: {gb_scores.mean():.4f} (+/- {gb_scores.std():.4f})")

        return results

    def _get_feature_importance(self) -> Dict:
        """Get feature importance from models"""
        importance_dict = {}

        threshold = self.config.get('feature_importance_threshold', 0.01)

        if self.model_type in ['random_forest', 'both'] and self.random_forest:
            importances = self.random_forest.feature_importances_
            rf_importance = {
                feature: importance
                for feature, importance in zip(self.feature_names, importances)
                if importance >= threshold
            }
            # Sort by importance
            rf_importance = dict(sorted(rf_importance.items(), key=lambda x: x[1], reverse=True))
            importance_dict['random_forest'] = rf_importance

        if self.model_type in ['gradient_boosting', 'both'] and self.gradient_boosting:
            importances = self.gradient_boosting.feature_importances_
            gb_importance = {
                feature: importance
                for feature, importance in zip(self.feature_names, importances)
                if importance >= threshold
            }
            # Sort by importance
            gb_importance = dict(sorted(gb_importance.items(), key=lambda x: x[1], reverse=True))
            importance_dict['gradient_boosting'] = gb_importance

        return importance_dict

    def save_models(self, model_dir: str = "models"):
        """
        Save trained models to disk

        Args:
            model_dir: Directory to save models
        """
        model_path = Path(model_dir)
        model_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save Random Forest
        if self.random_forest and self.model_type in ['random_forest', 'both']:
            rf_path = model_path / f"random_forest_{timestamp}.pkl"
            with open(rf_path, 'wb') as f:
                pickle.dump(self.random_forest, f)
            self.logger.info(f"Saved Random Forest model to {rf_path}")

        # Save Gradient Boosting
        if self.gradient_boosting and self.model_type in ['gradient_boosting', 'both']:
            gb_path = model_path / f"gradient_boosting_{timestamp}.pkl"
            with open(gb_path, 'wb') as f:
                pickle.dump(self.gradient_boosting, f)
            self.logger.info(f"Saved Gradient Boosting model to {gb_path}")

        # Save scaler
        scaler_path = model_path / f"scaler_{timestamp}.pkl"
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)

        # Save feature names
        features_path = model_path / f"features_{timestamp}.pkl"
        with open(features_path, 'wb') as f:
            pickle.dump(self.feature_names, f)

        self.logger.info(f"Models saved to {model_path}")

    def load_models(self, model_dir: str = "models", timestamp: str = None):
        """
        Load trained models from disk

        Args:
            model_dir: Directory containing models
            timestamp: Specific timestamp to load (loads latest if None)
        """
        model_path = Path(model_dir)

        if not model_path.exists():
            self.logger.error(f"Model directory not found: {model_dir}")
            return

        # Find latest models if timestamp not provided
        if timestamp is None:
            rf_files = list(model_path.glob("random_forest_*.pkl"))
            gb_files = list(model_path.glob("gradient_boosting_*.pkl"))

            if rf_files:
                rf_file = max(rf_files, key=lambda p: p.stat().st_mtime)
                timestamp = rf_file.stem.split('_', 2)[-1]
            elif gb_files:
                gb_file = max(gb_files, key=lambda p: p.stat().st_mtime)
                timestamp = gb_file.stem.split('_', 2)[-1]
            else:
                self.logger.error("No model files found")
                return

        # Load Random Forest
        rf_path = model_path / f"random_forest_{timestamp}.pkl"
        if rf_path.exists():
            with open(rf_path, 'rb') as f:
                self.random_forest = pickle.load(f)
            self.logger.info(f"Loaded Random Forest model from {rf_path}")

        # Load Gradient Boosting
        gb_path = model_path / f"gradient_boosting_{timestamp}.pkl"
        if gb_path.exists():
            with open(gb_path, 'rb') as f:
                self.gradient_boosting = pickle.load(f)
            self.logger.info(f"Loaded Gradient Boosting model from {gb_path}")

        # Load scaler
        scaler_path = model_path / f"scaler_{timestamp}.pkl"
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)

        # Load feature names
        features_path = model_path / f"features_{timestamp}.pkl"
        if features_path.exists():
            with open(features_path, 'rb') as f:
                self.feature_names = pickle.load(f)

        self.logger.info("Models loaded successfully")
