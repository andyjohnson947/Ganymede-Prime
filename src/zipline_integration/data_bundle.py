"""
MT5 Data Bundle for Zipline
Converts MT5 data to Zipline format
"""

import pandas as pd
import logging
from typing import Dict, List
from pathlib import Path


class MT5DataBundle:
    """Manages MT5 data conversion for Zipline"""

    def __init__(self, data_path: str = "data/trading_data.db"):
        """
        Initialize MT5 Data Bundle

        Args:
            data_path: Path to SQLite database with MT5 data
        """
        self.data_path = data_path
        self.logger = logging.getLogger(__name__)

    def convert_to_zipline_format(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """
        Convert MT5 DataFrame to Zipline format

        Args:
            df: DataFrame with MT5 OHLCV data (time as index)
            symbol: Trading symbol

        Returns:
            DataFrame in Zipline format
        """
        # Zipline expects specific column names
        zipline_df = pd.DataFrame({
            'open': df['open'],
            'high': df['high'],
            'low': df['low'],
            'close': df['close'],
            'volume': df.get('tick_volume', df.get('real_volume', df.get('volume', 0)))
        }, index=df.index)

        # Ensure timezone-aware datetime index
        if zipline_df.index.tz is None:
            zipline_df.index = zipline_df.index.tz_localize('UTC')

        # Sort by index
        zipline_df = zipline_df.sort_index()

        return zipline_df

    def create_bundle(
        self,
        data_dict: Dict[str, pd.DataFrame],
        output_path: str = None
    ) -> str:
        """
        Create a Zipline data bundle from MT5 data

        Args:
            data_dict: Dictionary of {symbol: DataFrame}
            output_path: Path to save bundle (optional)

        Returns:
            Path to created bundle
        """
        if output_path is None:
            output_path = "data/zipline_bundle"

        Path(output_path).mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Creating Zipline bundle at {output_path}")

        # Convert each symbol's data
        for symbol, df in data_dict.items():
            zipline_df = self.convert_to_zipline_format(df, symbol)

            # Save to CSV (Zipline can ingest from CSV)
            symbol_path = Path(output_path) / f"{symbol}.csv"
            zipline_df.to_csv(symbol_path)

            self.logger.info(f"Saved {symbol} data: {len(zipline_df)} bars")

        self.logger.info(f"Bundle created with {len(data_dict)} symbols")
        return output_path

    def load_from_storage(
        self,
        storage,
        symbols: List[str],
        timeframe: str = 'H1',
        bars: int = 10000
    ) -> Dict[str, pd.DataFrame]:
        """
        Load data from storage for bundle creation

        Args:
            storage: DataStorage instance
            symbols: List of symbols to load
            timeframe: Timeframe to load
            bars: Number of bars to load

        Returns:
            Dictionary of {symbol: DataFrame}
        """
        data_dict = {}

        for symbol in symbols:
            df = storage.get_price_data(symbol, timeframe, limit=bars)
            if df is not None and not df.empty:
                data_dict[symbol] = df
                self.logger.info(f"Loaded {len(df)} bars for {symbol}")
            else:
                self.logger.warning(f"No data found for {symbol}")

        return data_dict

    def get_bundle_info(self, bundle_path: str) -> Dict:
        """
        Get information about a bundle

        Args:
            bundle_path: Path to bundle directory

        Returns:
            Dictionary with bundle information
        """
        bundle_path = Path(bundle_path)
        if not bundle_path.exists():
            return {'error': 'Bundle not found'}

        csv_files = list(bundle_path.glob('*.csv'))

        info = {
            'path': str(bundle_path),
            'symbols': [f.stem for f in csv_files],
            'symbol_count': len(csv_files)
        }

        # Get date range for first symbol
        if csv_files:
            df = pd.read_csv(csv_files[0], index_col=0, parse_dates=True)
            info['start_date'] = df.index.min()
            info['end_date'] = df.index.max()
            info['total_bars'] = len(df)

        return info
