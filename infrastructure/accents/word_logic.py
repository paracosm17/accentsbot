import json
import os
from random import randint
from typing import List, Union

base_dir = os.path.dirname(os.path.abspath(__file__))
words_path = os.path.join(base_dir, "words.json")

with open(words_path, encoding="utf-8") as file:
    words = json.load(file)


class Word:
    def __init__(self, id: Union[int, str] = "random") -> None:
        self.data = words
        self.index = self.normalize_id(id)
        self.word: dict = self.data[self.index]
        self.id: int = self.word["id"]

    def normalize_id(self, id: Union[int, str]) -> int:
        if id == "random":
            return randint(0, len(self.data) - 1)

        if isinstance(id, int):
            if 1 <= id <= len(self.data):
                return id - 1
            raise IndexError(f"word id must be between 1 and {len(self.data)}")

        raise TypeError("id must be an integer or 'random'")

    @property
    def variants(self) -> List[str]:
        return self.word["variants"]

    @property
    def right(self) -> str:
        return self.word["right"]

    def get_all_words(self) -> List[str]:
        return [item["right"] for item in self.data]
