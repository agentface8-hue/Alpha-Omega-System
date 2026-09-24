"""Offline portfolio risk tests; market data deliberately unavailable."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

with patch.dict(sys.modules, {"yfinance": types.ModuleType("yfinance")}):
    portfolio = importlib.import_module("core.portfolio_manager")

from core import trading_safety


class PortfolioLimitsTests(unittest.TestCase):
    def test_minimum_size_never_overrides_risk_or_position_cap(self):
        for entry, stop in ((100, 50), (4000, 3900), (100, 100), (float("nan"), 95)):
            with self.subTest(entry=entry, stop=stop), self.assertRaises(ValueError):
                portfolio._size_position(entry, stop)

    def test_valid_sizing_obeys_limits_and_conserves_shares(self):
        for entry in (10, 100, 1000, 3000):
            sizing = portfolio._size_position(entry, entry * 0.95)
            self.assertLessEqual(sizing["risk_actual"], portfolio.MAX_RISK)
            self.assertLessEqual(sizing["position_size"], portfolio.MAX_POS_SIZE)
            self.assertEqual(sum(sizing[f"tp{i}_shares"] for i in (1, 2, 3)), sizing["shares"])

    def test_failed_safety_check_cannot_open_position(self):
        with patch.object(portfolio.store, "load_state", return_value={"cash": 25000}), \
             patch.object(portfolio.store, "load_positions", return_value=[]), \
             patch.dict(sys.modules, {"core.universe_builder": types.ModuleType("core.universe_builder")}), \
             patch.object(trading_safety, "check_trade_allowed", side_effect=OSError("unreadable")), \
             patch.object(portfolio, "_size_position", side_effect=AssertionError("must stop before sizing")):
            result = portfolio.open_position("TEST", 100, 95, 110, 120, 130)
            self.assertIn("Safety", result["error"])


if __name__ == "__main__":
    unittest.main()
