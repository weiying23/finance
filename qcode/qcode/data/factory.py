"""Data source factory.

Builds the appropriate `DataSource` adapter from a name, or a `SampleDataSource`
for offline testing. Also exposes `DataFetcher`, a backward-compatible factory
function that reads defaults from `config.DATA_CONFIG` so existing call sites
keep working and the source remains config-driven.
"""
from typing import Optional

from qcode.data.base import DataSource
from qcode.data.sample_source import SampleDataSource
from qcode.data.akshare_source import AkshareDataSource
from qcode.data.tushare_source import TushareDataSource
from qcode.data.baostock_source import BaostockDataSource
from qcode.data.yfinance_source import YfinanceDataSource

_SOURCES = {
    'akshare': AkshareDataSource,
    'tushare': TushareDataSource,
    'baostock': BaostockDataSource,
    'yfinance': YfinanceDataSource,
}


def create_data_source(use_sample_data: bool = False,
                       market_regime: str = 'bear',
                       source: str = 'akshare',
                       cache_data: bool = True,
                       tushare_token: str = '',
                       **kwargs) -> DataSource:
    """Create a data source.

    Args:
        use_sample_data: if True, return a SampleDataSource (no network/deps)
        market_regime: regime for sample data ('bear'|'bull'|'sideways'|'mixed')
        source: backend name when not using sample data
                ('akshare'|'tushare'|'baostock'|'yfinance')
        cache_data: enable in-memory caching
        tushare_token: tushare Pro token (only used by tushare backend)
    """
    if use_sample_data:
        return SampleDataSource(market_regime=market_regime, cache_data=cache_data)

    name = (source or 'akshare').lower()
    cls = _SOURCES.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown data source '{source}'. Available: {list(_SOURCES)}"
        )

    if name == 'tushare':
        return cls(cache_data=cache_data, token=tushare_token, market_regime=market_regime)
    if name == 'akshare':
        return cls(cache_data=cache_data, market_regime=market_regime)
    return cls(cache_data=cache_data, market_regime=market_regime)


def DataFetcher(use_sample_data: bool = False, market_regime: str = 'bear',
                cache_data: bool = True, source: Optional[str] = None,
                tushare_token: Optional[str] = None, **kwargs) -> DataSource:
    """Backward-compatible factory entry point.

    Reads defaults for `source` and `tushare_token` from `config.DATA_CONFIG`
    when available (lazily, so the data layer does not hard-depend on config),
    then delegates to `create_data_source`. Existing call sites such as
    ``DataFetcher(use_sample_data=..., market_regime=...)`` keep working and
    remain config-driven.
    """
    src = source
    token = tushare_token
    if src is None or token is None:
        try:
            from config import DATA_CONFIG
            if src is None:
                src = DATA_CONFIG.get('data_source', 'akshare')
            if token is None:
                token = DATA_CONFIG.get('tushare_token', '') or ''
        except Exception:
            src = src or 'akshare'
            token = token or ''
    return create_data_source(
        use_sample_data=use_sample_data,
        market_regime=market_regime,
        source=src,
        cache_data=cache_data,
        tushare_token=token,
    )
