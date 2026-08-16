"""baostock 财务数据(年度, quarter=4), pubDate 时点对齐 —— 消除前视偏差。

关键纪律: 财报只在 pubDate(发布日)之后才可知。align_to_daily 用 merge_asof
按 pubDate 前向填充到交易日, 发布日之前该值 = NaN(不可用)。

字段(全部来自年报):
  roe        ROE(净资产收益率, roeAvg)
  gp_margin  毛利率(gpMargin)
  debt_ratio 资产负债率(liabilityToAsset)
  yoy_ni     归母净利同比(YOYNI)

用法:
  from qcode.data.fundamental import attach_fundamentals
  engine.load_data(...)
  engine.market_data = attach_fundamentals(engine.market_data)   # 真实数据模式
"""
import os
import time

import pandas as pd

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          '.data_cache')

# API 名 → (字段名, 重命名)
_APIS = [
    ('query_profit_data', [('roeAvg', 'roe'), ('gpMargin', 'gp_margin')]),
    ('query_balance_data', [('liabilityToAsset', 'debt_ratio')]),
    ('query_growth_data', [('YOYNI', 'yoy_ni')]),
]


def _cache_path(symbol: str) -> str:
    return os.path.join(_CACHE_DIR, f"fundamental_{symbol}.csv")


def fetch_quarterly(symbol: str, start_year: int = 2018, end_year: int = 2025,
                    use_cache: bool = True) -> pd.DataFrame:
    """按年拉取年报财务(quarter=4), 返回按 pubDate 排序的 DataFrame, 有磁盘缓存。"""
    if use_cache and os.path.exists(_cache_path(symbol)):
        return pd.read_csv(_cache_path(symbol), parse_dates=['pubDate', 'statDate'])

    import baostock as bs
    bs.login()
    try:
        records = []
        for year in range(start_year, end_year + 1):
            for api_name, fields in _APIS:
                rs = getattr(bs, api_name)(code=f"sh.{symbol}" if symbol.startswith('6') or symbol.startswith('9') else f"sz.{symbol}",
                                           year=year, quarter=4)
                if rs.error_code != '0':
                    continue
                col_idx = {name: i for i, name in enumerate(rs.fields)}
                while rs.next():
                    row = rs.get_row_data()
                    rec = {'pubDate': row[col_idx['pubDate']], 'statDate': row[col_idx['statDate']]}
                    for src, dst in fields:
                        try:
                            rec[dst] = float(row[col_idx[src]] or 'nan')
                        except (ValueError, KeyError, IndexError):
                            rec[dst] = float('nan')
                    records.append(rec)
    finally:
        bs.logout()

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=['pubDate', 'statDate', 'roe', 'gp_margin', 'debt_ratio', 'yoy_ni'])
    df['pubDate'] = pd.to_datetime(df['pubDate'])
    df['statDate'] = pd.to_datetime(df['statDate'])
    # 3 个 API 各产生一条记录(只填自己的列), 按 (pubDate, statDate) 合并为每年一条(first 跳过 NaN)
    df = df.groupby(['pubDate', 'statDate'])[['roe', 'gp_margin', 'debt_ratio', 'yoy_ni']].first().reset_index()
    df = df.sort_values('pubDate')
    if use_cache:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        df.to_csv(_cache_path(symbol), index=False)
    return df


def align_to_daily(quarterly: pd.DataFrame, trading_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """按 pubDate 前向填充季度财务到交易日(发布日前不可用)。"""
    if quarterly.empty or len(trading_dates) == 0:
        cols = ['roe', 'gp_margin', 'debt_ratio', 'yoy_ni']
        return pd.DataFrame(index=trading_dates, columns=cols)
    daily = pd.DataFrame(index=trading_dates)
    for col in ['roe', 'gp_margin', 'debt_ratio', 'yoy_ni']:
        if col not in quarterly.columns:
            daily[col] = float('nan')
            continue
        src = quarterly[['pubDate', col]].dropna(subset=[col]).sort_values('pubDate')
        if src.empty:
            daily[col] = float('nan')
            continue
        merged = pd.merge_asof(daily.reset_index().rename(columns={'index': 'date'})[['date']]
                               .sort_values('date'),
                               src.rename(columns={col: f'{col}_v', 'pubDate': 'date'}),
                               on='date', direction='backward')
        daily[col] = merged[f'{col}_v'].values
    return daily


def attach_fundamentals(market_data: dict, use_cache: bool = True) -> dict:
    """把日频对齐的财务列并入各标的价格 df(真实数据模式用)。"""
    out = {}
    for sym, df in market_data.items():
        q = fetch_quarterly(sym, use_cache=use_cache)
        fund = align_to_daily(q, df.index)
        out[sym] = df.join(fund, how='left')
    return out


if __name__ == '__main__':
    t0 = time.time()
    df = fetch_quarterly('600519')
    print(f"600519 年报记录 {len(df)} 条, 耗时 {time.time()-t0:.1f}s")
    print(df.head(3).to_string())
