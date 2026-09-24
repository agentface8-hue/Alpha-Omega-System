"""Offline execution regressions. No broker, network or real state writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import order_executor as executor, trading_safety as safety


class ExecutionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.signal = dict(ticker="TEST", shares=10, entry=100, sl=95,
                           tp1=110, tp2=120, tp3=130)

    def execute(self, **changes):
        with patch.object(executor, "EXECUTOR_MODE", "paper"):
            return executor.execute_signal({**self.signal, **changes})

    def test_safety_failure_blocks_execution(self):
        with patch.object(safety, "check_trade_allowed", side_effect=OSError("unreadable")), \
             patch.object(executor, "_paper_execute") as paper:
            self.assertEqual(self.execute()["status"], "blocked")
            paper.assert_not_called()

    def test_safety_requires_explicit_allow(self):
        for response in ({}, {"allowed": "false"}, {"allowed": None}):
            with self.subTest(response=response), \
                 patch.object(safety, "check_trade_allowed", return_value=response):
                self.assertEqual(self.execute()["status"], "blocked")

    def test_invalid_orders_never_reach_execution(self):
        cases = [dict(entry=float("nan")), dict(sl=0), dict(tp2=105),
                 dict(tp3=float("inf")), dict(shares=1.5), dict(shares=True),
                 dict(shares="bad"), dict(tp1_shares=-1),
                 dict(tp1_shares=8, tp2_shares=8), dict(ticker=None),
                 dict(ticker=" "), dict(tp3_shares=99)]
        with patch.object(safety, "check_trade_allowed", return_value={"allowed": True}):
            for changes in cases:
                with self.subTest(changes=changes):
                    self.assertEqual(self.execute(**changes)["status"], "failed")

    def test_small_positions_conserve_shares(self):
        with patch.object(safety, "check_trade_allowed", return_value={"allowed": True}):
            for count in range(1, 21):
                result = self.execute(shares=count)
                self.assertEqual(result["status"], "filled")
                self.assertEqual(sum(result[f"tp{i}_shares"] for i in (1, 2, 3)), count)

    def test_unknown_mode_is_rejected(self):
        with patch.object(executor, "EXECUTOR_MODE", "typo"), \
             patch.object(safety, "check_trade_allowed", return_value={"allowed": True}):
            self.assertEqual(executor.execute_signal(self.signal)["status"], "failed")

    def test_unknown_broker_port_requires_live_acknowledgement(self):
        with patch.object(executor, "EXECUTOR_MODE", "ibkr"), \
             patch.object(executor, "IBKR_PORT", 4001), \
             patch.object(safety, "check_trade_allowed", return_value={"allowed": False}) as check:
            executor.execute_signal(self.signal)
            self.assertEqual(check.call_args.kwargs["mode"], "ibkr_live")

    def test_corrupt_safety_state_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "safety.json"
            with patch.object(safety, "SAFETY_FILE", path):
                for raw in ('{broken', '[]', '{"global_halt": "false"}',
                            '{"live_mode_confirmed": "true"}',
                            '{"halted_symbols": []}'):
                    path.write_text(raw)
                    self.assertFalse(safety.check_trade_allowed()["allowed"], raw)

    def test_missing_state_defaults_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(safety, "SAFETY_FILE", Path(tmp) / "absent.json"):
            first = safety.load_state()
            first["halted_symbols"]["TEST"] = {"reason": "test"}
            try:
                self.assertEqual(safety.load_state()["halted_symbols"], {})
            finally:
                safety.DEFAULT_STATE["halted_symbols"].clear()


if __name__ == "__main__":
    unittest.main()
