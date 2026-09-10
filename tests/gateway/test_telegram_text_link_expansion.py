"""Regression tests for Telegram hidden-link normalization."""

from types import SimpleNamespace

from plugins.platforms.telegram.adapter import TelegramAdapter


def _entity(entity_type, offset, length, url=None):
    return SimpleNamespace(type=entity_type, offset=offset, length=length, url=url)


def _message(**kwargs):
    values = dict(
        text=None,
        caption=None,
        entities=None,
        caption_entities=None,
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_text_link_is_inlined_with_utf16_offsets_after_emoji():
    message = _message(
        text="🔥 тут",
        entities=[_entity("text_link", 3, 3, "https://example.test/emoji")],
    )

    assert TelegramAdapter._expand_link_entities(message) == (
        "🔥 тут (https://example.test/emoji)"
    )


def test_caption_text_link_is_inlined():
    message = _message(
        caption="Смотри тут проект",
        caption_entities=[_entity("text_link", 7, 3, "https://example.test/project")],
    )

    assert TelegramAdapter._expand_link_entities(message) == (
        "Смотри тут (https://example.test/project) проект"
    )


def test_caption_media_link_uses_utf16_offsets_after_emoji():
    message = _message(
        caption="🔥 тут",
        caption_entities=[_entity("text_link", 3, 3, "https://example.test/media")],
    )

    assert TelegramAdapter._expand_link_entities(message) == (
        "🔥 тут (https://example.test/media)"
    )


def test_text_link_expansion_is_idempotent():
    entity = _entity("text_link", 8, 3, "https://example.test/project")
    first = TelegramAdapter._expand_link_entities(
        _message(text="Ссылка: тут", entities=[entity])
    )

    assert TelegramAdapter._expand_link_entities(
        _message(text=first, entities=[entity])
    ) == first


def test_multiple_text_links_after_emoji_are_inlined_once():
    entities = [
        _entity("text_link", 3, 3, "https://example.test/one"),
        _entity("text_link", 9, 3, "https://example.test/two"),
    ]
    first = TelegramAdapter._expand_link_entities(
        _message(text="🔥 тут и там", entities=entities)
    )

    assert first == "🔥 тут (https://example.test/one) и там (https://example.test/two)"
    assert TelegramAdapter._expand_link_entities(
        _message(text=first, entities=entities)
    ) == first


def test_duplicate_text_link_anchors_with_the_same_url_are_each_inlined_once():
    entities = [
        _entity("text_link", 0, 4, "https://example.test/same"),
        _entity("text_link", 9, 4, "https://example.test/same"),
    ]
    first = TelegramAdapter._expand_link_entities(
        _message(text="same and same", entities=entities)
    )

    assert first == (
        "same (https://example.test/same) and same (https://example.test/same)"
    )
    assert TelegramAdapter._expand_link_entities(
        _message(text=first, entities=entities)
    ) == first


def test_duplicate_caption_link_anchors_with_the_same_url_are_each_inlined_once():
    entities = [
        _entity("text_link", 0, 4, "https://example.test/same"),
        _entity("text_link", 9, 4, "https://example.test/same"),
    ]
    first = TelegramAdapter._expand_link_entities(
        _message(caption="same and same", caption_entities=entities)
    )

    assert first == (
        "same (https://example.test/same) and same (https://example.test/same)"
    )
    assert TelegramAdapter._expand_link_entities(
        _message(caption=first, caption_entities=entities)
    ) == first


def test_malformed_or_non_text_link_entities_are_ignored():
    message = _message(
        text="abc",
        entities=[
            _entity("bold", 0, 3),
            _entity("text_link", "bad", 1, "https://example.test/bad"),
            _entity("text_link", 1, 99, "https://example.test/past-end"),
        ],
    )

    assert TelegramAdapter._expand_link_entities(message) == "abc"
