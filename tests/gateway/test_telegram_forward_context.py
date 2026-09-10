"""Regression tests for Telegram forwarded-message provenance."""

from types import SimpleNamespace

from gateway.config import PlatformConfig
from gateway.platforms.event import MessageType
from plugins.platforms.telegram.adapter import TelegramAdapter


def _adapter():
    return TelegramAdapter(PlatformConfig(enabled=True, token="***", extra={}))


def _message(*, text="forwarded body", forward_origin=None, automatic=False):
    return SimpleNamespace(
        chat=SimpleNamespace(id=111, type="private", title=None, full_name="Alice"),
        from_user=SimpleNamespace(id=42, full_name="Alice", username="alice", is_bot=False),
        text=text,
        caption=None,
        entities=None,
        caption_entities=None,
        message_thread_id=None,
        message_id=1001,
        reply_to_message=None,
        quote=None,
        date=None,
        forum_topic_created=None,
        forward_origin=forward_origin,
        is_automatic_forward=automatic,
    )


def test_forward_from_user_is_normalized():
    origin = SimpleNamespace(
        type="user",
        date=None,
        sender_user=SimpleNamespace(id=99, full_name="Bob Jones", username="bobj"),
    )

    event = _adapter()._build_message_event(
        _message(text="check this out", forward_origin=origin), MessageType.TEXT
    )

    assert len(event.context_refs) == 1
    ref = event.context_refs[0]
    assert (ref.kind, ref.origin_type, ref.origin_name, ref.origin_id) == (
        "forward", "user", "Bob Jones", "99"
    )
    assert ref.origin_username == "bobj"
    assert event.text == "check this out"


def test_hidden_user_forward_is_confidence_limited():
    origin = SimpleNamespace(type="hidden_user", sender_user_name="Anonymous Coward")

    ref = _adapter()._build_message_event(
        _message(forward_origin=origin), MessageType.TEXT
    ).context_refs[0]

    assert ref.origin_type == "hidden_user"
    assert ref.origin_name == "Anonymous Coward"
    assert ref.origin_id is None
    assert ref.is_confidence_limited is True


def test_channel_forward_keeps_channel_and_original_message_id():
    origin = SimpleNamespace(
        type="channel",
        chat=SimpleNamespace(id=-1009, title="News Channel"),
        message_id=555,
        author_signature="Editor",
    )

    ref = _adapter()._build_message_event(
        _message(forward_origin=origin), MessageType.TEXT
    ).context_refs[0]

    assert (ref.origin_type, ref.origin_chat, ref.origin_id, ref.origin_message_id) == (
        "channel", "News Channel", "-1009", "555"
    )
    assert ref.origin_name == "Editor"


def test_automatic_forward_without_origin_is_marked():
    event = _adapter()._build_message_event(
        _message(forward_origin=None, automatic=True), MessageType.TEXT
    )

    assert [(ref.kind, ref.platform) for ref in event.context_refs] == [
        ("automatic_forward", "telegram")
    ]


def test_ordinary_message_has_no_context_refs():
    event = _adapter()._build_message_event(_message(), MessageType.TEXT)
    assert event.context_refs == []

