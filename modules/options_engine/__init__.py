"""
NEXUS AI — Options Engine (Module 3)

Implements complete options pricing models:
- Black-Scholes (analytical, fast)
- Binomial Tree (lattice, American options)
- Monte Carlo Simulation (path-dependent payoffs)
- Finite Difference Methods (PDE-based)
- Heston Stochastic Volatility Model
- Local Volatility (Dupire)
- SABR Model

All models share a common interface via OptionsPricer ABC.
Phase 3 will provide full implementations.
"""

from .black_scholes import BlackScholesPricer
from .greeks_engine import GreeksEngine
from .models import OptionSpec, PricingResult

__all__ = [
    "BlackScholesPricer",
    "GreeksEngine",
    "OptionSpec",
    "PricingResult",
]
