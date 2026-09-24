"""Exercise real JSON writers against temporary files only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import signal_store, portfolio_store, printing_store


class StorageDurabilityTests(unittest.TestCase):
    def test_replace_failure_preserves_previous_state(self):
        for writer in (signal_store._save_json, portfolio_store._jsave, printing_store._jsave):
            with self.subTest(writer=writer), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                path.write_text('{"cash": 25000}')
                with patch("os.replace", side_effect=OSError("disk unavailable")):
                    with self.assertRaises(OSError):
                        writer(path, {"cash": 100})
                self.assertEqual(json.loads(path.read_text()), {"cash": 25000})
                self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_corrupt_existing_state_is_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{broken')
            for read in (lambda: signal_store._load_json(path),
                         lambda: portfolio_store._jload(path, {}),
                         lambda: printing_store._jload(path, {})):
                with self.subTest(read=read), self.assertRaises(ValueError):
                    read()

    def test_unicode_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            value = {"note": "Avi — €", "cash": 25000}
            portfolio_store._jsave(path, value)
            self.assertEqual(portfolio_store._jload(path, {}), value)


if __name__ == "__main__":
    unittest.main()
