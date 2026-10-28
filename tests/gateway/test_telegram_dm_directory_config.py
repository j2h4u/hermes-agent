"""Telegram directory settings follow the selected config backend."""

from gateway.channel_directory import _load_configured_telegram_dm_topics
from hermes_cli.config_backend import ConfigBackendUnavailable


def test_topics_can_come_from_backend_without_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr("gateway.channel_directory.get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr("gateway.channel_directory.config_exists", lambda path: True)
    topics = [{"chat_id": "42", "topics": [{"name": "Reports", "thread_id": 7}]}]
    monkeypatch.setattr(
        "gateway.channel_directory.read_config_doc",
        lambda path: {"platforms": {"telegram": {"extra": {"dm_topics": topics}}}},
    )

    assert _load_configured_telegram_dm_topics() == topics


def test_backend_outage_does_not_exit_directory_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("gateway.channel_directory.get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr("gateway.channel_directory.config_exists", lambda path: True)

    def unavailable(path):
        raise ConfigBackendUnavailable("remote config unavailable")

    monkeypatch.setattr("gateway.channel_directory.read_config_doc", unavailable)

    assert _load_configured_telegram_dm_topics() == []
