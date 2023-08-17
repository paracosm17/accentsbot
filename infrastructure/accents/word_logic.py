import os
import json
from random import randint
from typing import List

base_dir = os.path.dirname(os.path.abspath(__file__))
words_path = os.path.join(base_dir, "words.json")
with open(words_path, "r", encoding="utf-8") as file:
    words = json.load(file)


class Word:
    def __init__(self, id: int = "random") -> None:
        self.data = words
        self.id = self.normalize_id(id)
        self.word: dict = self.data[self.id]

    def normalize_id(self, id: int):
        if id == "random":
            return randint(1, len(self.data) - 1)
        if isinstance(id, int):
            if 0 < int(id) < len(self.data):
                return int(id)
            raise IndexError
        raise TypeError

    @property
    def variants(self) -> List[str]:
        return self.word["variants"]

    @property
    def right(self) -> str:
        return self.word["right"]

    def get_all_words(self):
        return [i["right"] for i in self.data]
