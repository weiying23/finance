"""IC 月度监控: 定期重跑因子/信号 IC, 记录历史趋势, 及时发现因子失效。

背景: volatility 反转因子是"时段性"结论(低波因子在 A 股会翻转),
momentum 等在样本数据与真实数据的结论相反——所以 IC 要定期复测,
而不是测一次就永远相信。

用法:
  python monitor_ic.py                                  # 跑一次并追加到 monitoring/ic_history.csv
  python monitor_ic.py --symbols 600519 000858          # 自选标的(默认 50 只池)
  python monitor_ic.py --start 2019-01-01 --end 2023-12-31   # 自定义区间(默认最近2年)
  python monitor_ic.py --show                           # 只看历史趋势, 不重跑

定时(每周一 09:00, crontab):
  0 9 * * 1 cd /Users/yingwei/Documents/code/finance/qcode && .venv/bin/python monitor_ic.py >> monitoring/monitor.log 2>&1

输出 monitoring/ic_history.csv(每次一行):
  run_date, symbols, start, end,
  alpha_ic5, alpha_ic10, alpha_ic20, alpha_icir5,      # multi_factor 合成信号
  value_ic20, volatility_ic20,                          # 关键因子
  mom_ic5, mrev_ic5, masset_ic5, mf_ic5, sarb_ic5, regime_ic5,  # 各策略信号 IC@5
  pair1_ic20, pair2_ic20, pair3_ic20                    # 配对 IC@20
"""
import argparse
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import STOCK_UNIVERSE, PAIRS_TRADING_STRATEGY, MULTI_FACTOR_ALPHA
from qcode.strategies.alpha_mining import MultiFactorAlpha
from qcode.utils.significance import factor_ic_report
from factor_report import load_data, FACTORS, FORWARD_PERIODS
from signal_report import build_strategies, compute_strategy_ic, pairs_signal_ic

MONITOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'monitoring')
HISTORY_CSV = os.path.join(MONITOR_DIR, 'ic_history.csv')

# 监控重点: multi_factor 合成信号 + 关键因子 + 各策略信号 + 配对
MF_FACTORS = ['alpha_score', 'value_score', 'volatility_score',
              'turnover_score', 'reversal_score', 'amihud_score', 'pb_score', 'pe_score']
STRATEGY_KEYS = {'momentum': 'mom', 'mean_reversion': 'mrev', 'multi_asset': 'masset',
                 'multi_factor': 'mf', 'stat_arb': 'sarb', 'regime': 'regime'}
HEADERS = (['run_date', 'symbols', 'start', 'end']
           + [f'alpha_ic{fp}' for fp in FORWARD_PERIODS] + ['alpha_icir5']
           + ['value_ic20', 'volatility_ic20']
           + [f'{k}_ic5' for k in STRATEGY_KEYS.values()]
           + [f'pair{i}_ic20' for i in range(1, 4)])


def default_period() -> tuple:
    """默认最近 2 年(到本周一为止)。"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=365 * 2)
    return start.isoformat(), end.isoformat()


def collect(data) -> dict:
    row = {}
    # multi_factor 因子/合成信号
    strat = MultiFactorAlpha(**MULTI_FACTOR_ALPHA)
    indicated = {s: strat.calculate_indicators(df) for s, df in data.items()}
    rep = factor_ic_report(indicated, MF_FACTORS, forward_periods=FORWARD_PERIODS)
    a = rep.get('alpha_score', {})
    for fp in FORWARD_PERIODS:
        row[f'alpha_ic{fp}'] = round(a.get(fp, {}).get('mean_ic', 0.0), 4)
    row['alpha_icir5'] = round(a.get(5, {}).get('ic_ir', 0.0), 3)
    row['value_ic20'] = round(rep.get('value_score', {}).get(20, {}).get('mean_ic', 0.0), 4)
    row['volatility_ic20'] = round(rep.get('volatility_score', {}).get(20, {}).get('mean_ic', 0.0), 4)
    # 各策略信号 IC@5
    for name, (s, _) in build_strategies().items():
        r = compute_strategy_ic(name, s, data)
        row[f'{STRATEGY_KEYS[name]}_ic5'] = round(r.get('score', {}).get(5, {}).get('mean_ic', 0.0), 4)
    # 配对 IC@20
    pairs = PAIRS_TRADING_STRATEGY.get('pairs', [])
    pair_rows = pairs_signal_ic(data, pairs)
    for i, (_, ic_row) in enumerate(pair_rows, start=1):
        if i <= 3:
            row[f'pair{i}_ic20'] = round(ic_row[2], 4)  # fp=20 是第 3 个
    return row


def show_history(rows: int = 12):
    if not os.path.exists(HISTORY_CSV):
        print(f"无历史记录: {HISTORY_CSV}")
        return
    with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    if not data:
        print("历史记录为空")
        return
    print(f"共 {len(data)} 次记录, 显示最近 {rows} 次:\n")
    print(f"{'run_date':<12}{'区间':<26}{'alphaIC5':>9}{'alphaIC20':>10}{'alphaICIR':>10}{'value20':>9}{'vol20':>9}")
    print("-" * 88)
    for r in data[-rows:]:
        print(f"{r['run_date']:<12}{r['start']+'~'+r['end']:<26}"
              f"{r.get('alpha_ic5','?'):>9}{r.get('alpha_ic20','?'):>10}"
              f"{r.get('alpha_icir5','?'):>10}{r.get('value_ic20','?'):>9}{r.get('volatility_ic20','?'):>9}")
    # 简单趋势提示
    alphas = [float(r['alpha_ic20']) for r in data if r.get('alpha_ic20', '?') != '?']
    if len(alphas) >= 2:
        trend = "上行" if alphas[-1] > alphas[0] else "下行"
        print(f"\nalpha IC@20 从 {alphas[0]:+.4f} → {alphas[-1]:+.4f} ({trend})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--symbols', nargs='+', default=None, help='标的(默认 50 只池)')
    ap.add_argument('--start', default=None, help='区间起点(默认最近2年)')
    ap.add_argument('--end', default=None, help='区间终点(默认今天)')
    ap.add_argument('--show', action='store_true', help='只看历史趋势')
    args = ap.parse_args()

    if args.show:
        show_history()
        return

    start, end = args.start, args.end
    if not start or not end:
        d1, d2 = default_period()
        start, end = start or d1, end or d2
    symbols = args.symbols or STOCK_UNIVERSE

    print(f"IC 监控采样: {len(symbols)} 只 | {start} ~ {end}")
    data = load_data(sample=False, regime='', symbols=symbols, start=start, end=end)
    row = collect(data)
    row.update({'run_date': datetime.date.today().isoformat(), 'symbols': str(len(symbols)),
                'start': start, 'end': end})

    os.makedirs(MONITOR_DIR, exist_ok=True)
    new_file = not os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    print(f"已记录 → {HISTORY_CSV}")
    print(f"  alpha_score IC@5={row['alpha_ic5']:+.4f} IC@20={row['alpha_ic20']:+.4f} "
          f"ICIR@5={row['alpha_icir5']:+.3f} | value IC@20={row['value_ic20']:+.4f} "
          f"| vol IC@20={row['volatility_ic20']:+.4f}")
    print()
    show_history(rows=6)


if __name__ == '__main__':
    main()
