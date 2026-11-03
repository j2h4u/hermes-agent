"""The Meet plugin asks Playwright to enable Chromium's sandbox."""

import sys
from types import ModuleType
from unittest.mock import MagicMock


def test_meet_bot_uses_chromium_sandbox(tmp_path, monkeypatch):
    from plugins.google_meet import meet_bot

    chromium = MagicMock()
    chromium.launch.side_effect = RuntimeError("stop after launch")
    playwright = MagicMock()
    playwright.__enter__.return_value.chromium = chromium
    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: playwright
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    monkeypatch.setenv("HERMES_MEET_URL", "https://meet.google.com/abc-defg-hij")
    monkeypatch.setenv("HERMES_MEET_OUT_DIR", str(tmp_path))
    monkeypatch.setenv("HERMES_MEET_MODE", "transcribe")
    assert meet_bot.run_bot() == 1
    assert chromium.launch.call_args.kwargs["chromium_sandbox"] is True


def test_meet_auth_uses_chromium_sandbox(tmp_path, monkeypatch):
    from plugins.google_meet import cli

    chromium = MagicMock()
    chromium.launch.side_effect = RuntimeError("stop after launch")
    playwright = MagicMock()
    playwright.__enter__.return_value.chromium = chromium
    sync_api = ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: playwright
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    monkeypatch.setattr(cli, "_auth_state_path", lambda: tmp_path / "auth.json")
    assert cli._cmd_auth() == 1
    assert chromium.launch.call_args.kwargs["chromium_sandbox"] is True
