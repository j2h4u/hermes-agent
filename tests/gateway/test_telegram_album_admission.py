"""Telegram media merges retain every attachment through durable native admission."""

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


class TestTelegramAlbumAdmission(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = TemporaryDirectory(prefix="hermes-album-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.enterContext(patch.dict(os.environ, {
            "HERMES_HOME": str(self.root), "TELEGRAM_ALLOWED_USERS": "album-user",
        }))

        from gateway.config import GatewayConfig, Platform, PlatformConfig
        from gateway.platforms import base
        from gateway.run import GatewayRunner
        from gateway.session_authority import initialize_session_authority
        from plugins.platforms.telegram.adapter import TelegramAdapter

        self.enterContext(patch.object(base, "DOCUMENT_CACHE_DIR", self.root / "documents"))
        runner = GatewayRunner(GatewayConfig(sessions_dir=self.root / "sessions"))
        self.adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
        self.adapter.gateway_runner = runner
        self.adapter.handle_message = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: self.adapter}
        self.authority = await initialize_session_authority(
            runner, profile_id="default", instance_id="album-test")
        self.addCleanup(self.authority.db.close)
        self.authority._schedule = lambda ref: None
        self.source = self.adapter.build_source(
            chat_id="album-chat", user_id="album-user", chat_type="dm", thread_id="album-topic")

    async def _assert_saved(self, event, contents, flags):
        from gateway.session_envelope import restore_native
        from hermes_state_runtime import list_session_admissions

        receipt = await self.authority.admit_native(event)
        rows = list_session_admissions(
            self.authority.db, session_id=receipt.ref.session_id, pending_only=False)
        self.assertEqual(len(rows), 1)
        restored = restore_native(rows[0]["payload"])
        self.assertEqual(restored.media_text_inlined, flags)
        self.assertEqual([Path(path).read_bytes() for path in restored.media_urls], contents)
        self.assertEqual(restored.source.thread_id, "album-topic")

    async def test_two_pdf_album_is_saved_with_both_attachments(self):
        from gateway.platforms.event import MessageEvent, MessageType

        contents = [b"%PDF-1.4 first document", b"%PDF-1.4 second document"]
        self.adapter.MEDIA_GROUP_WAIT_SECONDS = 60
        try:
            for index, content in enumerate(contents):
                event = MessageEvent(text="read both", source=self.source,
                                     message_type=MessageType.DOCUMENT, message_id=str(index))
                doc = SimpleNamespace(
                    file_name=f"document-{index}.pdf", mime_type="application/pdf", file_size=len(content),
                    get_file=AsyncMock(return_value=SimpleNamespace(
                        download_as_bytearray=AsyncMock(return_value=bytearray(content)))))
                self.assertFalse(await self.adapter._cache_inbound_document(SimpleNamespace(document=doc), event))
                await self.adapter._queue_media_group_event("pdf-album", event)
        finally:
            tasks = list(self.adapter._media_group_tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.adapter._media_group_tasks.clear()
        self.adapter.MEDIA_GROUP_WAIT_SECONDS = 0
        await self.adapter._flush_media_group_event("pdf-album")
        self.adapter.handle_message.assert_awaited_once()
        await self._assert_saved(self.adapter.handle_message.await_args.args[0], contents, [False, False])

    async def test_text_batch_keeps_legacy_and_explicit_inline_flags_aligned(self):
        from gateway.platforms.base import BasePlatformAdapter
        from gateway.platforms.event import MessageEvent, MessageType

        contents = [b"legacy attachment", b"already inlined text"]
        events = []
        for index, content in enumerate(contents):
            path = self.root / f"notes-{index}.txt"
            path.write_bytes(content)
            events.append(MessageEvent(
                text=content.decode(), source=self.source, message_id=str(index),
                message_type=MessageType.TEXT, media_urls=[str(path)], media_types=["text/plain"],
                media_text_inlined=[] if index == 0 else [True]))
        try:
            for event in events:
                BasePlatformAdapter._enqueue_text_event(self.adapter, event)
        finally:
            tasks = list(self.adapter._pending_text_batch_tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(len(self.adapter._pending_text_batches), 1)
        event = next(iter(self.adapter._pending_text_batches.values()))
        await self._assert_saved(event, contents, [None, True])
