"""
ML Predictor
Uses trained models to generate trading predictions
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from .model_trainer import MLModelTrainer
from .feature_engineer import FeatureEngineer


class MLPredictor:
    """Generates predictions using trained ML models"""

    def __init__(self, trainer: MLModelTrainer):
        """
        Initialize ML Predictor

        Args:
            trainer: Trained MLModelTrainer instance
        """
        self.trainer = trainer
        self.feature_engineer = trainer.feature_engineer
        self.logger = logging.getLogger(__name__)

        self.prediction_threshold = trainer.config.get('prediction_threshold', 0.6)

    def predict(
        self,
        df: pd.DataFrame,
        model_type: str = None
    ) -> Tuple[int, float, Dict]:
        """
        Generate prediction for current market state

        Args:
            df: DataFrame with recent price data and indicators
            model_type: 'random_forest', 'gradient_boosting', or None (uses config)

        Returns:
            Tuple of (signal, confidence, details)
            signal: 1 (buy), -1 (sell), 0 (hold)
            confidence: Prediction confidence (0-1)
            details: Dictionary with prediction details
        """
        # Determine which model to use
        if model_type is None:
            model_type = self.trainer.model_type

        # Engineer features
        df_features = self.feature_engineer.engineer_all_features(df)

        # Get latest row
        latest_data = df_features.iloc[[-1]]

        # Select features
        feature_cols = [col for col in self.trainer.feature_names if col in latest_data.columns]
        X = latest_data[feature_cols]

        # Handle missing features
        missing_features = set(self.trainer.feature_names) - set(feature_cols)
        if missing_features:
            self.logger.warning(f"Missing features: {missing_features}")
            # Add missing columns with zeros
            for feature in missing_features:
                X[feature] = 0

        # Ensure correct column order
        X = X[self.trainer.feature_names]

        # Scale features
        X_scaled = self.trainer.scaler.transform(X)

        # Get prediction and probability
        if model_type == 'random_forest':
            model = self.trainer.random_forest
        elif model_type == 'gradient_boosting':
            model = self.trainer.gradient_boosting
        else:
            # Use both and ensemble
            return self._ensemble_predict(X_scaled)

        if model is None:
            self.logger.error(f"Model {model_type} not trained")
            return 0, 0.0, {'error': 'Model not trained'}

        # Predict
        prediction = model.predict(X_scaled)[0]
        probabilities = model.predict_proba(X_scaled)[0]

        # Get confidence
        confidence = max(probabilities)

        # Generate signal
        signal = self._generate_signal(prediction, confidence)

        details = {
            'prediction': int(prediction),
            'confidence': float(confidence),
            'probabilities': {
                'down': float(probabilities[0]),
                'up': float(probabilities[1])
            },
            'model_type': model_type,
            'timestamp': datetime.now()
        }

        self.logger.info(f"Prediction: {signal} (confidence: {confidence:.2f})")

        return signal, confidence, details

    def _ensemble_predict(self, X_scaled: np.ndarray) -> Tuple[int, float, Dict]:
        """
        Generate ensemble prediction from both models

        Args:
            X_scaled: Scaled feature array

        Returns:
            Tuple of (signal, confidence, details)
        """
        predictions = []
        confidences = []
        all_probs = []

        # Random Forest prediction
        if self.trainer.random_forest:
            rf_pred = self.trainer.random_forest.predict(X_scaled)[0]
            rf_proba = self.trainer.random_forest.predict_proba(X_scaled)[0]
            predictions.append(rf_pred)
            confidences.append(max(rf_proba))
            all_probs.append(rf_proba)

        # Gradient Boosting prediction
        if self.trainer.gradient_boosting:
            gb_pred = self.trainer.gradient_boosting.predict(X_scaled)[0]
            gb_proba = self.trainer.gradient_boosting.predict_proba(X_scaled)[0]
            predictions.append(gb_pred)
            confidences.append(max(gb_proba))
            all_probs.append(gb_proba)

        if not predictions:
            return 0, 0.0, {'error': 'No models available'}

        # Ensemble: average probabilities
        avg_probs = np.mean(all_probs, axis=0)
        ensemble_pred = np.argmax(avg_probs)
        ensemble_confidence = max(avg_probs)

        # Generate signal
        signal = self._generate_signal(ensemble_pred, ensemble_confidence)

        details = {
            'prediction': int(ensemble_pred),
            'confidence': float(ensemble_confidence),
            'probabilities': {
                'down': float(avg_probs[0]),
                'up': float(avg_probs[1])
            },
            'model_type': 'ensemble',
            'individual_predictions': predictions,
            'individual_confidences': confidences,
            'timestamp': datetime.now()
        }

        self.logger.info(f"Ensemble Prediction: {signal} (confidence: {ensemble_confidence:.2f})")

        return signal, confidence, details

    def _generate_signal(self, prediction: int, confidence: float) -> int:
        """
        Generate trading signal from prediction

        Args:
            prediction: Model prediction (0=down, 1=up)
            confidence: Prediction confidence

        Returns:
            Signal: 1 (buy), -1 (sell), 0 (hold)
        """
        if confidence < self.prediction_threshold:
            return 0  # Hold (not confident enough)

        if prediction == 1:
            return 1  # Buy
        else:
            return -1  # Sell

    def batch_predict(
        self,
        df: pd.DataFrame,
        lookback: int = 100
    ) -> pd.DataFrame:
        """
        Generate predictions for multiple time steps

        Args:
            df: DataFrame with price data and indicators
            lookback: Number of bars to use for feature calculation

        Returns:
            DataFrame with predictions added
        """
        self.logger.info(f"Generating batch predictions for {len(df)} bars...")

        # Engineer features for entire dataframe
        df_features = self.feature_engineer.engineer_all_features(df)

        predictions = []
        confidences = []

        # Generate prediction for each row (after lookback period)
        for i in range(lookback, len(df_features)):
            # Get data up to current point
            current_df = df_features.iloc[:i+1]

            # Get features for current row
            feature_cols = [col for col in self.trainer.feature_names if col in current_df.columns]
            X = current_df.iloc[[-1]][feature_cols]

            # Handle missing features
            for feature in self.trainer.feature_names:
                if feature not in X.columns:
                    X[feature] = 0

            # Ensure correct order
            X = X[self.trainer.feature_names]

            # Scale and predict
            X_scaled = self.trainer.scaler.transform(X)

            # Use configured model
            if self.trainer.model_type == 'random_forest':
                model = self.trainer.random_forest
            elif self.trainer.model_type == 'gradient_boosting':
                model = self.trainer.gradient_boosting
            else:
                # Use random forest as default for batch
                model = self.trainer.random_forest

            if model:
                pred = model.predict(X_scaled)[0]
                proba = model.predict_proba(X_scaled)[0]
                conf = max(proba)

                signal = self._generate_signal(pred, conf)
                predictions.append(signal)
                confidences.append(conf)
            else:
                predictions.append(0)
                confidences.append(0.0)

        # Pad with zeros for lookback period
        predictions = [0] * lookback + predictions
        confidences = [0.0] * lookback + confidences

        # Add to dataframe
        df['ml_signal'] = predictions
        df['ml_confidence'] = confidences

        self.logger.info("Batch predictions complete")
        return df

    def get_prediction_summary(self, signal: int, confidence: float, details: Dict) -> str:
        """
        Get human-readable summary of prediction

        Args:
            signal: Trading signal
            confidence: Prediction confidence
            details: Prediction details dictionary

        Returns:
            Summary string
        """
        signal_map = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}
        signal_str = signal_map.get(signal, 'UNKNOWN')

        summary = f"""
ML Prediction Summary:
---------------------
Signal: {signal_str}
Confidence: {confidence:.2%}
Model: {details.get('model_type', 'Unknown')}

Probabilities:
  Up (Buy):    {details.get('probabilities', {}).get('up', 0):.2%}
  Down (Sell): {details.get('probabilities', {}).get('down', 0):.2%}

Timestamp: {details.get('timestamp', 'N/A')}
"""

        if details.get('model_type') == 'ensemble':
            summary += f"\nIndividual Models: {len(details.get('individual_predictions', []))}"

        return summary
