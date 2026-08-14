"""Factor significance testing utilities"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

def calculate_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float:
    """Information Coefficient: Pearson correlation between factor and forward returns"""
    if len(factor_values) < 5 or len(forward_returns) < 5:
        return 0.0
    combined = pd.DataFrame({'factor': factor_values, 'return': forward_returns}).dropna()
    if len(combined) < 5:
        return 0.0
    return combined['factor'].corr(combined['return'])


def calculate_rank_ic(factor_values: pd.Series, forward_returns: pd.Series) -> float:
    """Rank IC: Spearman rank correlation between factor and forward returns"""
    if len(factor_values) < 5 or len(forward_returns) < 5:
        return 0.0
    combined = pd.DataFrame({'factor': factor_values, 'return': forward_returns}).dropna()
    if len(combined) < 5:
        return 0.0
    return combined['factor'].corr(combined['return'], method='spearman')


def bonferroni_correction(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """Bonferroni multiple test correction"""
    threshold = alpha / len(p_values) if len(p_values) > 0 else alpha
    return [p < threshold for p in p_values]


def fdr_correction(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """Benjamini-Hochberg FDR correction"""
    n = len(p_values)
    if n == 0:
        return []

    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    results = [False] * n

    for rank_i, (orig_idx, p_val) in enumerate(indexed):
        bh_threshold = alpha * (rank_i + 1) / n
        results[orig_idx] = p_val < bh_threshold

    for i in range(n - 2, -1, -1):
        rank_i_current = sorted(range(n), key=lambda j: p_values[j])[i]
        rank_i_next = sorted(range(n), key=lambda j: p_values[j])[i + 1]
        if not results[rank_i_next]:
            results[rank_i_current] = False

    return results


def calculate_factor_significance(data: Dict[str, pd.DataFrame],
                                  factor_names: List[str],
                                  forward_period: int = 5) -> Dict[str, Dict]:
    """Calculate IC and significance for multiple factors"""
    results = {}

    all_factors = pd.DataFrame()
    for symbol, df in data.items():
        temp = df[['close']].copy()
        temp['forward_return'] = temp['close'].pct_change(forward_period).shift(-forward_period)
        for factor in factor_names:
            if factor in df.columns:
                temp[factor] = df[factor]
        temp['symbol'] = symbol
        all_factors = pd.concat([all_factors, temp])

    for factor in factor_names:
        if factor not in all_factors.columns:
            continue

        ic_values = []
        p_values = []

        for symbol in data.keys():
            symbol_data = all_factors[all_factors['symbol'] == symbol].dropna()
            if len(symbol_data) < 10:
                continue

            ic = calculate_ic(symbol_data[factor], symbol_data['forward_return'])
            ic_values.append(ic)

            from scipy.stats import pearsonr
            if len(symbol_data[factor]) > 2 and len(symbol_data['forward_return']) > 2:
                _, p = pearsonr(symbol_data[factor], symbol_data['forward_return'])
                p_values.append(p)

        mean_ic = np.mean(ic_values) if ic_values else 0
        ic_std = np.std(ic_values) if len(ic_values) > 1 else 0
        ic_ir = mean_ic / ic_std if ic_std > 0 else 0

        significant_bh = fdr_correction(p_values) if p_values else []

        results[factor] = {
            'mean_ic': mean_ic,
            'ic_std': ic_std,
            'ic_ir': ic_ir,
            'num_tests': len(p_values),
            'num_significant_bh': sum(significant_bh),
            'p_values': p_values
        }

    return results


def factor_ic_report(data: Dict[str, pd.DataFrame], factor_names: List[str],
                     forward_periods: Tuple[int, ...] = (5, 10, 20)) -> Dict[str, Dict[int, Dict]]:
    """多周期因子 IC 报告: 每个因子 × 每个 forward_period 的 mean_IC / ICIR / FDR 显著数。

    机构惯例: 先看因子对未来收益有无预测力(IC), 再看是否稳定(ICIR), 再看是否运气(FDR),
    全部通过才允许进入组合。返回结构 {factor: {forward_period: calculate_factor_significance 单期结果}}。
    """
    report: Dict[str, Dict[int, Dict]] = {}
    for fp in forward_periods:
        per_period = calculate_factor_significance(data, factor_names, forward_period=fp)
        for factor, res in per_period.items():
            report.setdefault(factor, {})[fp] = res
    return report


def suggest_weights(report: Dict[str, Dict[int, Dict]], forward_period: int = 5,
                    min_icir: float = 0.3) -> Tuple[Dict[str, float], List[str]]:
    """按 ICIR 建议因子权重(替代拍脑袋权重)。

    规则:
      - 只保留 mean_IC > 0 且 ICIR >= min_icir 的因子(有正预测力且稳定);
      - 权重 ∝ ICIR(越大越可靠权重越高), 归一化;
      - 显著反向的因子(|ICIR| 达标但 mean_IC < 0)与无效因子一并列入 dropped,
        报告中可见, 建议反向使用或剔除。
    返回 (建议权重 dict, 剔除/反向因子列表)。
    """
    weights: Dict[str, float] = {}
    dropped: List[str] = []
    for factor, per_fp in report.items():
        r = per_fp.get(forward_period)
        if not r:
            dropped.append(factor)
            continue
        mean_ic = r.get('mean_ic', 0.0)
        ic_ir = r.get('ic_ir', 0.0)
        if mean_ic > 0 and ic_ir >= min_icir:
            weights[factor] = ic_ir
        else:
            dropped.append(factor)
    total = sum(weights.values())
    if total <= 0:
        return {}, dropped
    return {f: w / total for f, w in weights.items()}, dropped
