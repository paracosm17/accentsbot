import html
import json
import os
from random import choice, randint, shuffle
from typing import Literal, Optional

base_dir = os.path.dirname(os.path.abspath(__file__))
paronyms_path = os.path.join(base_dir, "paronyms.json")

with open(paronyms_path, encoding="utf-8") as file:
    paronym_groups = json.load(file)

TaskKind = Literal["meaning", "context"]


class ParonymTask:
    """One fast training task for EGE task 5 paronyms.

    Public id is 1-based and stable for callback_data, exactly like Word.id in accents.
    The task itself is encoded as term_index + kind, because one paronym group has several correct answers.
    """

    def __init__(
        self,
        group_id: int | str = "random",
        term_index: Optional[int] = None,
        kind: Optional[TaskKind] = None,
    ) -> None:
        self.data = paronym_groups
        self.index = self.normalize_group_id(group_id)
        self.group = self.data[self.index]
        self.id: int = self.group["id"]

        if term_index is None:
            term_index = randint(0, len(self.group["terms"]) - 1)
        if not 0 <= term_index < len(self.group["terms"]):
            raise IndexError("term_index is out of range")

        self.term_index = term_index
        self.term = self.group["terms"][self.term_index]
        self.kind: TaskKind = kind or choice(["meaning", "context"])

    def normalize_group_id(self, group_id: int | str) -> int:
        if group_id == "random":
            return randint(0, len(self.data) - 1)
        if isinstance(group_id, int):
            if 1 <= group_id <= len(self.data):
                return group_id - 1
            raise IndexError(f"paronym group id must be between 1 and {len(self.data)}")
        raise TypeError("group_id must be an integer or 'random'")

    @property
    def right(self) -> str:
        return self.term["word"]

    @property
    def variants(self) -> list[str]:
        variants = [item["word"] for item in self.group["terms"]]
        shuffle(variants)
        return variants

    @property
    def question(self) -> str:
        if self.kind == "context":
            return f"Выберите подходящий пароним:\n\n{self.mask_example(self.term['example'])}"
        return f"Выберите пароним по значению:\n\n{self.term['meaning']}"

    @property
    def explanation(self) -> str:
        lines = [
            f"<b>{item['word']}</b> — {item['meaning']}" for item in self.group["terms"]
        ]
        return "\n".join(lines)

    @property
    def explanation_with_examples(self) -> str:
        """
        Красивое HTML-сообщение для Telegram:
        слово + краткое значение + пример.
        """
        lines = []

        for term in self.group["terms"]:
            word = html.escape(term["word"])
            meaning = html.escape(term["meaning"])
            example = html.escape(term.get("example", ""))

            lines.append(f"📘 <b>{word}</b> — {meaning}")

            if example:
                lines.append(f"<i>Пример:</i> {example}")

            lines.append("")

        return "\n".join(lines).strip()

    def mask_example(self, example: str) -> str:
        word = self.term["word"]
        lower = word.lower()
        candidates = {word, lower, word.capitalize()}
        for candidate in sorted(candidates, key=len, reverse=True):
            if candidate in example:
                return example.replace(candidate, "<b>_____</b>", 1)
        return f"<b>_____</b>. {example}"

    def callback_payload(self) -> str:
        return f"{self.id}_{self.term_index}_{self.kind}"

    @classmethod
    def from_payload(cls, payload: str) -> "ParonymTask":
        # aiogram CallbackData uses ':' as an internal separator,
        # so our field value must not contain ':'.
        # New safe format: groupId_termIndex_kind, example: 109_0_meaning.
        # Old ':' format is accepted defensively for tests/manual calls,
        # but it must never be packed into CallbackData.
        separator = "_" if "_" in payload else ":"
        group_id, term_index, kind = payload.split(separator, maxsplit=2)
        return cls(int(group_id), int(term_index), kind)  # type: ignore[arg-type]

    def get_all_words(self) -> list[str]:
        result: list[str] = []
        for group in self.data:
            for term in group["terms"]:
                result.append(term["word"])
        return result
