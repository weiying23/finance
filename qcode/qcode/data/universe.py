"""Point-in-time universe selection by liquidity (no look-ahead bias).

Selects the top-N most liquid A-shares as of a given date, using only data
in the lookback window IMMEDIATELY BEFORE that date. This avoids the
survivorship/look-ahead bias of selecting the universe by end-of-sample
liquidity and then backtesting earlier periods.

**已知偏差(无法用 baostock 根除)**:候选池来自 `baostock.query_hs300_stocks()`,
返回的是**当前**沪深 300 成分股名单,退市/被剔除的股票不在池中 → 仍有**幸存者偏差**。
本模块只解决了"流动性时点"前视,成分名单的幸存者偏差需历史成分数据(tushare 可查)
才能完全消除。结论应定性不定量。
"""
import os
from datetime import timedelta
from typing import List

import pandas as pd


def _hs300_candidates() -> pd.DataFrame:
    """Return current HS300 constituents via baostock (cols: code, code_name)."""
    import baostock as bs
    bs.login()
    try:
        rs = bs.query_hs300_stocks()
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=rs.fields)
    finally:
        bs.logout()


def select_liquidity_universe(as_of: str, top_n: int = 50, lookback_days: int = 60,
                              source: str = 'baostock',
                              cache_dir: str = '.data_cache') -> List[str]:
    """Select top-N most liquid A-shares as of `as_of` (uses only data BEFORE as_of).

    Args:
        as_of: reference date (YYYY-MM-DD); selection window is the
               `lookback_days` immediately preceding it.
        top_n: number of stocks to return.
        lookback_days: window length in calendar days before as_of.
        source: data backend for turnover lookup ('baostock'|'akshare'|'tushare').
        cache_dir: disk cache dir for the selected universe list.

    Returns:
        List of 6-digit stock codes, ranked by average daily turnover (desc).
    """
    as_of_ts = pd.to_datetime(as_of)
    start = (as_of_ts - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end = as_of_ts.strftime('%Y-%m-%d')

    cache_key = f"universe_{source}_{top_n}_{lookback_days}_{as_of_ts.strftime('%Y%m%d')}"
    cache_path = os.path.join(cache_dir, f"{cache_key}.csv")
    if os.path.exists(cache_path):
        # dtype=str 保留前导零(000063 否则会被读成 int 63)
        return pd.read_csv(cache_path, dtype={'code': str})['code'].tolist()

    cand = _hs300_candidates()  # code like 'sh.600000'
    from qcode.data.factory import create_data_source
    ds = create_data_source(source=source, cache_data=True)

    recs = []
    for code in cand['code'].tolist():
        sym = code.split('.')[-1]
        name = cand.loc[cand['code'] == code, 'code_name'].iloc[0]
        df = ds.get_stock_daily(sym, start, end)
        if df is not None and not df.empty and 'amount' in df.columns:
            amt = pd.to_numeric(df['amount'], errors='coerce').mean()
        else:
            amt = 0
        recs.append((sym, name, amt if pd.notna(amt) else 0))

    df = pd.DataFrame(recs, columns=['code', 'name', 'avg_amount'])
    df = df.sort_values('avg_amount', ascending=False).reset_index(drop=True)
    top = df.head(top_n)

    os.makedirs(cache_dir, exist_ok=True)
    top[['code', 'name']].to_csv(cache_path, index=False)
    return top['code'].tolist()


if __name__ == '__main__':
    import sys
    as_of = sys.argv[1] if len(sys.argv) > 1 else '2019-01-01'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    codes = select_liquidity_universe(as_of, top_n=n)
    print(f"{len(codes)} stocks as of {as_of}:")
    print(codes)
