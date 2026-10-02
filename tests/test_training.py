from __future__ import annotations

import pytest

from infrastructure.accents.accent import render_telegram_html
from infrastructure.accents.word_logic import Word
from infrastructure.paronyms.paronym_logic import ParonymTask


def test_word_ids_are_one_based() -> None:
    first = Word(1)
    assert first.id == first.word["id"]
    assert first.right in first.variants


def test_word_rejects_out_of_range_id() -> None:
    with pytest.raises(IndexError):
        Word(0)


def test_paronym_callback_round_trip() -> None:
    original = ParonymTask(1, term_index=0, kind="meaning")
    restored = ParonymTask.from_payload(original.callback_payload())

    assert restored.id == original.id
    assert restored.term_index == original.term_index
    assert restored.kind == original.kind
    assert restored.right == original.right


def test_user_text_is_escaped_for_telegram_html() -> None:
    assert render_telegram_html('<b>hello & "world"</b>') == (
        "&lt;b&gt;hello &amp; &quot;world&quot;&lt;/b&gt;"
    )
