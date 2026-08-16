"""行业分类(baostock query_stock_industry), 用于截面选股的行业中性约束。

缓存到 .data_cache/industry_map.csv, 避免每次重拉。
返回 {6位代码: 行业名}。
"""
import os

import pandas as pd

CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          '.data_cache', 'industry_map.csv')


def load_industry_map(cache_path: str = CACHE_PATH) -> dict:
    """加载 6 位代码 → 行业名 映射(baostock 当前行业分类, 有缓存)。"""
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
        return dict(zip(df['code'], df['industry']))

    import baostock as bs
    bs.login()
    try:
        rs = bs.query_stock_industry()
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return {}
        df = pd.DataFrame(rows, columns=rs.fields)  # code / code_name / industry / industryClassification
        df['code'] = df['code'].str.split('.').str[-1]  # 'sh.600519' -> '600519'
    finally:
        bs.logout()

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df[['code', 'industry']].to_csv(cache_path, index=False)
    return dict(zip(df['code'], df['industry']))


if __name__ == '__main__':
    m = load_industry_map()
    print(f"{len(m)} 只股票行业映射, 示例: {list(m.items())[:5]}")
