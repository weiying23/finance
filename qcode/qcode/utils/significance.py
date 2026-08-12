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
