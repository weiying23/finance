"""Sample/synthetic data source for offline testing.

Generates realistic OHLCV data across four market regimes (bear, bull,
sideways, mixed). Requires no network access and no third-party data library,
so ``python main.py --sample-data`` works in a bare environment.
"""
import pandas as pd
import numpy as np

from qcode.data.base import DataSource


class SampleDataSource(DataSource):
    """Generate synthetic OHLCV data for offline testing across market regimes.

    Reproducible per-symbol via a local RandomState seeded by the symbol code,
    so backtest results are deterministic for a given regime.
    """

    def __init__(self, market_regime: str = 'bear', cache_data: bool = True):
        super().__init__(cache_data=cache_data, use_sample_data=True,
                         market_regime=market_regime)

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._generate_sample_data(symbol, start_date, end_date, self.market_regime)

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._generate_sample_data(index_code, start_date, end_date, self.market_regime)

    def get_futures_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._generate_sample_data(symbol, start_date, end_date, self.market_regime)

    def _generate_sample_data(self, symbol: str, start_date: str, end_date: str,
                              market_regime: str = 'bear') -> pd.DataFrame:
        """Generate realistic sample data for offline testing.

        Args:
            symbol: Stock code (used to seed the RNG for reproducibility)
            start_date: Start date string
            end_date: End date string
            market_regime: 'bear' (all stocks drop), 'bull' (all stocks rise),
                           'sideways' (flat), or 'mixed' (some up some down)
        """
        start = pd.to_datetime(start_date.replace('-', ''))
        end = pd.to_datetime(end_date.replace('-', ''))
        dates = pd.date_range(start, end, freq='B')

        rng = np.random.RandomState(int(symbol) if symbol.isdigit() else 42)
        n = len(dates)

        base_price = 1500 if symbol == '600519' else 100
        returns = np.zeros(n)

        if market_regime == 'bear':
            for i in range(n):
                if rng.random() < 0.1:
                    returns[i] = rng.normal(-0.02, 0.03)
                else:
                    returns[i] = rng.normal(-0.001, 0.015)
        elif market_regime == 'bull':
            for i in range(n):
                if rng.random() < 0.10:
                    returns[i] = rng.normal(0.004, 0.020)
                else:
                    returns[i] = rng.normal(0.001, 0.015)
        elif market_regime == 'sideways':
            for i in range(n):
                if rng.random() < 0.3:
                    returns[i] = rng.normal(-0.001, 0.025)
                else:
                    returns[i] = rng.normal(0.0003, 0.02)
        elif market_regime == 'mixed':
            stock_num = int(symbol) if symbol.isdigit() else 0
            group = stock_num % 3
            if group == 0:
                for i in range(n):
                    returns[i] = rng.normal(0.002, 0.015)
            elif group == 1:
                for i in range(n):
                    returns[i] = rng.normal(-0.001, 0.015)
            else:
                for i in range(n):
                    returns[i] = rng.normal(0.0003, 0.02)
        else:
            returns = rng.normal(0.0005, 0.02, n)

        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'open': prices * (1 + rng.uniform(-0.01, 0.01, n)),
            'high': prices * (1 + np.abs(rng.uniform(0, 0.02, n))),
            'low': prices * (1 - np.abs(rng.uniform(0, 0.02, n))),
            'close': prices,
            'volume': rng.randint(1000000, 10000000, n),
            'amount': prices * rng.randint(1000000, 10000000, n),
            'amplitude': rng.uniform(1, 5, n),
            'pct_change': returns * 100,
            'change': returns * prices,
            'turnover': rng.uniform(0.1, 5, n),
            'symbol': symbol
        }, index=dates)
        df.index.name = 'date'
        return df
