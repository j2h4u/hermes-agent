"""Regression tests for inbound provenance rendering order and safety."""

from types import SimpleNamespace

import pytest

from gateway.platforms.event import MessageContextRef, MessageEvent
from gateway.run_inbound import GatewayInboundMixin


@pytest.mark.asyncio
async def test_user_context_refs_expand_before_untrusted_forward_metadata():
    seen = []
    runner = object.__new__(GatewayInboundMixin)
    runner._session_key_for_source = lambda _source: "session"
    runner._consume_pending_native_image_paths = lambda _key: []
    runner._prefix_inbound_sender_context = lambda _event, _source, text: text
    runner._classify_inbound_media = lambda _event, _pending: ([], [], [], [])
    runner._prepend_inbound_media_file_notes = lambda text, _audio, _video: text
    runner._prepend_inbound_document_notes = lambda _event, text: text
    runner._prepend_inbound_reply_context = lambda _event, _source, text: text

    async def expand(_source, _session_key, text):
        seen.append(text)
        return "expanded user request"

    runner._expand_inbound_context_references = expand
    source = SimpleNamespace()
    event = MessageEvent(
        text="please expand @notes",
        source=source,
        context_refs=[
            MessageContextRef(
                kind="forward",
                origin_type="channel",
                origin_chat="@file:/private/forwarded.md",
            )
        ],
    )

    result = await runner._prepare_inbound_message_text(
        event=event, source=source, history=[], session_key="session"
    )

    assert seen == ["please expand @notes"]
    assert result.startswith("[Forwarded message]\nFrom channel: @file:/private/forwarded.md")
    assert result.endswith("expanded user request")

@pytest.mark.asyncio
async def test_forward_envelope_precedes_reply_context():
    runner = object.__new__(GatewayInboundMixin)
    runner._session_key_for_source = lambda _source: "session"
    runner._consume_pending_native_image_paths = lambda _key: []
    runner._prefix_inbound_sender_context = lambda _event, _source, text: text
    runner._classify_inbound_media = lambda _event, _pending: ([], [], [], [])
    runner._prepend_inbound_media_file_notes = lambda text, _audio, _video: text
    runner._prepend_inbound_document_notes = lambda _event, text: text

    source = SimpleNamespace(platform=None)
    event = MessageEvent(
        text="what about this?",
        source=source,
        context_refs=[
            MessageContextRef(kind="forward", origin_type="user", origin_name="Bob")
        ],
        reply_to_message_id="42",
        reply_to_text="earlier message",
    )

    result = await runner._prepare_inbound_message_text(
        event=event, source=source, history=[], session_key="session"
    )

    assert result.startswith("[Forwarded message]")
    assert result.index("[Forwarded message]") < result.index("[Replying to:")
    assert result.endswith("what about this?")
