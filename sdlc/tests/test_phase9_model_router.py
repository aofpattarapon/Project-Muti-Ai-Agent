"""
Phase 9.4 Tests — hermes3 last-resort cooldown hardening

Covers:
  - best_free_for_role() still returns ollama/hermes3 when ollama is in cooldown
  - best_free_for_role() logs warning when hermes3 used despite ollama cooldown
  - ModelRouter.route() still returns ollama/hermes3 when all providers cooling
  - ModelRouter.route() logs warning when ollama is in cooldown at last-resort

Run: python3 sdlc/tests/test_phase9_model_router.py
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.model_router import best_free_for_role, ModelRouter


# ─── best_free_for_role() ─────────────────────────────────────────────────────

class TestBestFreeForRoleFallback(unittest.TestCase):
    """best_free_for_role() always falls back to hermes3; warns when ollama cooling."""

    def test_returns_hermes3_when_no_providers_available(self):
        """Ultimate fallback returns ollama/hermes3 even when no providers are reachable."""
        with patch("shared.model_router._get_available_providers_cached", return_value=set()):
            key, cfg = best_free_for_role("dev")
        self.assertEqual(key, "ollama/hermes3")
        self.assertEqual(cfg.provider, "ollama")

    def test_warns_when_ollama_in_exclude_providers(self):
        """Logs WARNING when hermes3 fallback fires and ollama is in exclude_providers."""
        with patch("shared.model_router._get_available_providers_cached", return_value=set()):
            with self.assertLogs("shared.model_router", level="WARNING") as cm:
                key, cfg = best_free_for_role("dev", exclude_providers=["ollama"])
        self.assertEqual(key, "ollama/hermes3")
        self.assertTrue(
            any("hermes3 last-resort" in msg and "ollama cooldown" in msg for msg in cm.output),
            f"Expected cooldown warning in logs, got: {cm.output}",
        )

    def test_no_warning_when_ollama_not_in_exclude_providers(self):
        """No WARNING emitted when ollama is not excluded (not cooling)."""
        with patch("shared.model_router._get_available_providers_cached", return_value=set()):
            # assertLogs raises AssertionError when no logs are emitted — that's the pass condition
            try:
                with self.assertLogs("shared.model_router", level="WARNING"):
                    key, cfg = best_free_for_role("dev")
                self.fail("Expected no WARNING logs but some were emitted")
            except AssertionError:
                pass  # correct — no warnings
        self.assertEqual(key, "ollama/hermes3")


# ─── ModelRouter.route() ─────────────────────────────────────────────────────

class TestModelRouterLastResort(unittest.TestCase):
    """ModelRouter.route() last-resort hermes3 warns when ollama provider is cooling."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DB_PATH"] = os.path.join(self._tmpdir.name, "test.db")
        with patch("shared.model_router.ModelRouter._check_available_providers"):
            self.router = ModelRouter()
        self.router._available_providers = set()  # no providers reachable

    def tearDown(self):
        self._tmpdir.cleanup()
        os.environ.pop("DB_PATH", None)

    def test_returns_hermes3_when_all_unavailable(self):
        """route() returns ollama/hermes3 as last resort when no providers available."""
        with patch("shared.model_router._active_cooldown_blocks", return_value=(set(), set())):
            with patch.object(self.router.tracker, "is_over_budget", return_value=False):
                cfg, key, _ = self.router.route("write some code", role="dev")
        self.assertEqual(key, "ollama/hermes3")

    def test_warns_when_ollama_cooling_at_last_resort(self):
        """Logs WARNING when hermes3 last-resort fires and ollama is in active cooldown."""
        with patch("shared.model_router._active_cooldown_blocks", return_value=({"ollama"}, set())):
            with patch.object(self.router.tracker, "is_over_budget", return_value=False):
                with self.assertLogs("shared.model_router", level="WARNING") as cm:
                    cfg, key, _ = self.router.route("write some code", role="dev")
        self.assertEqual(key, "ollama/hermes3")
        self.assertTrue(
            any("hermes3 last-resort" in msg and "ollama cooldown" in msg for msg in cm.output),
            f"Expected cooldown warning in logs, got: {cm.output}",
        )

    def test_no_warning_when_ollama_not_cooling_at_last_resort(self):
        """No WARNING when hermes3 is used as last resort but ollama is not cooling."""
        with patch("shared.model_router._active_cooldown_blocks", return_value=(set(), set())):
            with patch.object(self.router.tracker, "is_over_budget", return_value=False):
                try:
                    with self.assertLogs("shared.model_router", level="WARNING"):
                        cfg, key, _ = self.router.route("write some code", role="dev")
                    self.fail("Expected no WARNING logs but some were emitted")
                except AssertionError:
                    pass  # correct — no warnings
        self.assertEqual(key, "ollama/hermes3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
