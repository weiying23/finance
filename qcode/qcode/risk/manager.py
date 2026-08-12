"""Risk management with delta hedging, Greeks, and portfolio optimization"""
import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd


@dataclass
class Greeks:
    """Option Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class RiskManager:
    """Manage portfolio risk with delta hedging, position sizing, and optimization"""

    def __init__(self, max_position_size: float = 0.1,
                 max_portfolio_var: float = 0.02,
                 risk_free_rate: float = 0.03,
                 stop_loss_pct: float = 0.02,
                 target_portfolio_vol: float = 0.15):
        self.max_position_size = max_position_size
        self.max_portfolio_var = max_portfolio_var
        self.risk_free_rate = risk_free_rate
        self.stop_loss_pct = stop_loss_pct
        self.target_portfolio_vol = target_portfolio_vol

    def calculate_position_size(self, portfolio_value: float,
                                entry_price: float,
                                stop_loss_pct: float = None,
                                confidence: float = 1.0,
                                volatility: Optional[float] = None) -> int:
        """Calculate position size with confidence and volatility adjustment"""
        if stop_loss_pct is None:
            stop_loss_pct = self.stop_loss_pct

        max_position_value = portfolio_value * self.max_position_size
        max_shares_by_value = int(max_position_value / entry_price)

        risk_per_share = entry_price * stop_loss_pct
        max_portfolio_risk = portfolio_value * self.max_portfolio_var
        max_shares_by_risk = int(max_portfolio_risk / risk_per_share) if risk_per_share > 0 else max_shares_by_value

        base_size = min(max_shares_by_value, max_shares_by_risk)
        if confidence is None or np.isnan(confidence):
            confidence = 1.0
        adjusted_size = int(base_size * confidence)
        return max(adjusted_size, 0)

    def calculate_risk_parity_weights(self, volatilities: Dict[str, float]) -> Dict[str, float]:
        """Risk parity: w_i proportional to 1/sigma_i"""
        inv_vols = {k: 1.0 / v for k, v in volatilities.items() if v > 0}
        if not inv_vols:
            n = len(volatilities)
            return {k: 1.0 / n for k in volatilities}
        total = sum(inv_vols.values())
        return {k: v / total for k, v in inv_vols.items()}

    def calculate_portfolio_volatility(self, weights: Dict[str, float],
                                       returns_df: pd.DataFrame) -> float:
        """Portfolio volatility: sigma_p = sqrt(w' Sigma w)"""
        symbols = list(weights.keys())
        w = np.array([weights.get(s, 0.0) for s in symbols])
        if len(symbols) == 0 or len(returns_df) < 2:
            return 0.0
        cov_matrix = returns_df[symbols].cov().values
        portfolio_var = w @ cov_matrix @ w
        return np.sqrt(portfolio_var) * np.sqrt(252)

    def _ledoit_wolf_shrinkage(self, returns_df: pd.DataFrame,
                               shrinkage_alpha: float = 0.5) -> np.ndarray:
        """Manual Ledoit-Wolf shrinkage: Sigma_shrunk = alpha * sigma^2_avg * I + (1-alpha) * Sigma_sample"""
        sample_cov = returns_df.cov().values
        n_assets = sample_cov.shape[0]
        avg_var = np.mean(np.diag(sample_cov))
        target = avg_var * np.eye(n_assets)
        shrunk = shrinkage_alpha * target + (1 - shrinkage_alpha) * sample_cov
        return shrunk

    def calculate_min_variance_weights(self, returns_df: pd.DataFrame,
                                       max_weight: float = 0.15,
                                       shrinkage_alpha: float = 0.5) -> Dict[str, float]:
        """Minimum variance optimization: min w'Sigma w, constraints sum(w)=1, w>=0, w<=max_weight"""
        symbols = returns_df.columns.tolist()
        n = len(symbols)
        if n < 2:
            return {symbols[0]: 1.0} if n == 1 else {}

        cov_matrix = self._ledoit_wolf_shrinkage(returns_df, shrinkage_alpha)

        def objective(w):
            return w @ cov_matrix @ w

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, max_weight) for _ in range(n)]
        initial_w = np.ones(n) / n

        result = minimize(objective, initial_w, method='SLSQP',
                          bounds=bounds, constraints=constraints,
                          options={'ftol': 1e-10, 'maxiter': 200})

        if result.success:
            weights = {symbols[i]: result.x[i] for i in range(n)}
        else:
            weights = {s: 1.0 / n for s in symbols}

        return weights

    def calculate_option_greeks(self, spot: float, strike: float,
                                time_to_maturity: float, volatility: float,
                                option_type: str = 'call') -> Greeks:
        """Calculate option Greeks using Black-Scholes"""
        r = self.risk_free_rate

        d1 = (np.log(spot / strike) + (r + 0.5 * volatility**2) * time_to_maturity) / \
             (volatility * np.sqrt(time_to_maturity))
        d2 = d1 - volatility * np.sqrt(time_to_maturity)

        if option_type == 'call':
            delta = norm.cdf(d1)
            rho = strike * time_to_maturity * np.exp(-r * time_to_maturity) * norm.cdf(d2) / 100
        else:
            delta = -norm.cdf(-d1)
            rho = -strike * time_to_maturity * np.exp(-r * time_to_maturity) * norm.cdf(-d2) / 100

        gamma = norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_maturity))

        theta_call = (-spot * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_maturity)) -
                     r * strike * np.exp(-r * time_to_maturity) * norm.cdf(d2)) / 365
        theta_put = (-spot * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_maturity)) +
                    r * strike * np.exp(-r * time_to_maturity) * norm.cdf(-d2)) / 365
        theta = theta_call if option_type == 'call' else theta_put

        vega = spot * norm.pdf(d1) * np.sqrt(time_to_maturity) / 100

        return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)

    def calculate_portfolio_delta(self, positions: Dict, current_prices: Dict) -> float:
        """Calculate total portfolio delta"""
        total_delta = 0.0

        for pos_key, position in positions.items():
            if position.asset_type == 'stock':
                stock_delta = position.quantity if position.position_type == 'long' else -position.quantity
                total_delta += stock_delta
            elif position.asset_type == 'option':
                if all(hasattr(position, attr) for attr in ['strike', 'expiry', 'option_type']):
                    time_to_maturity = (position.expiry - pd.Timestamp.now()).days / 365.0
                    if time_to_maturity > 0:
                        volatility = position.metadata.get('volatility', 0.3)
                        greeks = self.calculate_option_greeks(
                            position.current_price, position.strike,
                            time_to_maturity, volatility, position.option_type
                        )
                        option_delta = greeks.delta * position.quantity * 100
                        if position.position_type == 'short':
                            option_delta *= -1
                        total_delta += option_delta

        return total_delta

    def calculate_delta_hedge(self, portfolio_delta: float,
                             underlying_price: float) -> Tuple[str, int]:
        """Calculate required hedge to neutralize portfolio delta"""
        if abs(portfolio_delta) < 0.01:
            return ('hold', 0)

        hedge_quantity = int(abs(portfolio_delta))

        if portfolio_delta > 0:
            return ('sell', hedge_quantity)
        else:
            return ('buy', hedge_quantity)

    def check_risk_limits(self, position_value: float, portfolio_value: float) -> bool:
        """Check if position respects risk limits"""
        position_pct = position_value / portfolio_value if portfolio_value > 0 else 0
        return position_pct <= self.max_position_size

    def calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if len(returns) == 0:
            return 0.0
        return np.percentile(returns, (1 - confidence) * 100)

    def calculate_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)"""
        if len(returns) == 0:
            return 0.0
        var = self.calculate_var(returns, confidence)
        tail = returns[returns <= var]
        return tail.mean() if len(tail) > 0 else 0.0

    def calculate_position_correlation(self, returns1: pd.Series,
                                       returns2: pd.Series) -> float:
        """Calculate correlation between two positions"""
        if len(returns1) < 2 or len(returns2) < 2:
            return 0.0
        return returns1.corr(returns2)

    def optimize_kelly_criterion(self, win_rate: float,
                                win_loss_ratio: float) -> float:
        """Calculate optimal position size using Kelly Criterion"""
        if win_loss_ratio <= 0:
            return 0.0
        kelly_pct = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        return max(0, min(kelly_pct * 0.5, self.max_position_size))
