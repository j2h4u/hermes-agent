"""Forward provenance survives durable command turns and gateway restarts."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from gateway.config import Platform
from gateway.platforms.event import MessageContextRef, MessageEvent
from gateway.session import SessionSource
from gateway.session_envelope import _snapshot_native, restore_native


@pytest.mark.parametrize('date', [None, datetime(2026, 10, 21, tzinfo=timezone.utc)])
def test_forward_context_survives_durable_roundtrip(date):
    source = SessionSource(platform=Platform.TELEGRAM, chat_id='c1', user_id='u1')
    ref = MessageContextRef(kind='forward', origin_type='user', origin_name='Alice',
                            date=date, text='original', is_confidence_limited=True)
    event = MessageEvent(text='queued follow-up', source=source, context_refs=[ref])
    runner = SimpleNamespace(session_store=SimpleNamespace(_generate_session_key=lambda _: 'route'))
    payload = _snapshot_native(runner, event, None, encoded_source={**source.to_dict(), 'is_bot': False})
    restored = restore_native(json.loads(json.dumps(payload)))
    assert restored.context_refs == [ref]
    assert restored.context_refs[0] is not ref
    event.context_refs.clear()
    plain = _snapshot_native(runner, event, None, encoded_source={**source.to_dict(), 'is_bot': False})
    assert 'context_refs' not in plain['native_text_v1']['event']
