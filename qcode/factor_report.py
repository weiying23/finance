"""多因子 IC 检验报告(Phase A 接入)。

对 MultiFactorAlpha 的每个因子做 IC/ICIR/FDR 显著性检验(多 forward period),
输出"有效因子 + 建议权重(按 ICIR)", 供 config.MULTI_FACTOR_ALPHA 参考。

机构惯例: 因子先过 IC 检验再进组合。IC≈0 的因子(无论回测收益多好)都是
市场 beta 或参数拟合, 不是 alpha。本脚本把"拍脑袋权重"变成"检验驱动权重"。

用法:
  python factor_report.py                        # sample 数据(mixed 环境, 默认)
  python factor_report.py --regime bear          # sample 其他市场环境
  python factor_report.py --real --symbols 600519 000858  # 真实数据(需联网, 走 config 数据源)
"""
import argparse
import sys

import pandas as pd

sys.path.insert(0, '.')

from config import STOCK_UNIVERSE
from qcode.data.sample_source import SampleDataSource
from qcode.strategies.alpha_mining import MultiFactorAlpha
from qcode.utils.significance import factor_ic_report, suggest_weights

FACTORS = ['momentum_score', 'value_score', 'volatility_score', 'volume_score', 'alpha_score']
FORWARD_PERIODS = (5, 10, 20)
MIN_ICIR = 0.3


def load_data(sample: bool, regime: str, symbols, start: str, end: str):
    if sample:
        ds = SampleDataSource(market_regime=regime)
        return ds.get_multiple_stocks(symbols, start, end)
    from qcode.data.factory import create_data_source
    ds = create_data_source(cache_data=True)
    return ds.get_multiple_stocks(symbols, start, end)


def fmt_ic(v: float) -> str:
    return f"{v:+.4f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--real', action='store_true', help='用真实数据(默认 sample)')
    ap.add_argument('--regime', default='mixed', choices=['bear', 'bull', 'sideways', 'mixed'],
                    help='sample 数据市场环境(仅 --real 未开时生效)')
    ap.add_argument('--symbols', nargs='+', default=None, help='标的(默认 sample: 演示池 / real: 50只池)')
    ap.add_argument('--start', default='2022-01-01')
    ap.add_argument('--end', default='2023-12-31')
    ap.add_argument('--min-icir', type=float, default=MIN_ICIR, help=f'建议权重最低 ICIR(默认 {MIN_ICIR})')
    args = ap.parse_args()

    symbols = args.symbols or (['600519', '000858', '600036', '601318', '000333', '600887',
                                '601012', '000651', '601901', '600030', '601288', '000625']
                               if not args.real else STOCK_UNIVERSE)

    print(f"数据: {'sample(' + args.regime + ')' if not args.real else 'real'} | "
          f"{len(symbols)} 只 | {args.start} ~ {args.end}\n")

    data = load_data(not args.real, args.regime, symbols, args.start, args.end)
    strat = MultiFactorAlpha()
    indicated = {s: strat.calculate_indicators(df) for s, df in data.items()}

    report = factor_ic_report(indicated, FACTORS, forward_periods=FORWARD_PERIODS)

    # --- 表头: 因子 | IC@5 | IC@10 | IC@20 | ICIR@5 | FDR显著@5 ---
    print(f"{'因子':<18}" + ''.join(f"{f'IC@{fp}':>9}" for fp in FORWARD_PERIODS)
          + f"{'ICIR@5':>9}{'FDR显著@5':>12}")
    print("-" * (18 + 9 * len(FORWARD_PERIODS) + 9 + 12))
    for f in FACTORS:
        row = report.get(f, {})
        ic_strs = ''.join(fmt_ic(row.get(fp, {}).get('mean_ic', 0.0)) for fp in FORWARD_PERIODS)
        r5 = row.get(5, {})
        print(f"{f:<18}{ic_strs}{r5.get('ic_ir', 0.0):>9.3f}"
              f"{str(r5.get('num_significant_bh', 0)) + '/' + str(r5.get('num_tests', 0)):>12}")
    print()

    # --- 建议权重 ---
    for fp in FORWARD_PERIODS:
        weights, dropped = suggest_weights(report, forward_period=fp, min_icir=args.min_icir)
        print(f"建议权重(@{fp}日, ICIR>={args.min_icir}):")
        if weights:
            for f, w in sorted(weights.items(), key=lambda x: -x[1]):
                print(f"    {f:<18}{w:.3f}")
        else:
            print("    无有效因子(IC 不显著或为负)——当前合成信号缺乏预测力, 建议换因子或接受 beta 策略定位")
        if dropped:
            print(f"    剔除/反向: {', '.join(dropped)}")
        print()

    # --- 结论判词 ---
    r5 = report.get('alpha_score', {}).get(5, {})
    ic5 = r5.get('mean_ic', 0.0)
    if abs(ic5) < 0.02:
        verdict = "alpha_score 在 5 日周期无预测力(IC≈0): 回测收益大概率来自市场 beta 与参数拟合, 不是因子 alpha。"
    elif ic5 > 0:
        verdict = f"alpha_score 有正预测力(IC={ic5:+.4f}), 但需结合 ICIR 与样本外验证判断是否可交易。"
    else:
        verdict = f"alpha_score 为负预测力(IC={ic5:+.4f}): 信号方向与未来收益相反, 需检查因子方向或反转使用。"
    print(f"判词: {verdict}")


if __name__ == '__main__':
    main()
