from __future__ import annotations

import html
import pickle
from functools import lru_cache
from pathlib import Path

import spacy
from spacy.language import Language

BASE_DIR = Path(__file__).resolve().parent


def render_telegram_html(text: str) -> str:
    """Escape arbitrary text for the bot-wide Telegram HTML parse mode."""
    return html.escape(text)


LEMMAS_PATH = BASE_DIR / "lemmas.dat"
WORDFORMS_PATH = BASE_DIR / "wordforms.dat"


@lru_cache(maxsize=1)
def _nlp() -> Language:
    return spacy.load("ru_core_news_md")


@lru_cache(maxsize=1)
def _accent_data() -> tuple[dict, dict]:
    with LEMMAS_PATH.open("rb") as stream:
        lemmas = pickle.load(stream)
    with WORDFORMS_PATH.open("rb") as stream:
        wordforms = pickle.load(stream)
    return lemmas, wordforms


class Accenter:
    def __init__(self, text: str):
        self.text = text
        self.lemmas, self.wordforms = _accent_data()

    def compatible(self, interpretation: str, lemma: str, tag: str) -> bool:
        if lemma in self.lemmas:
            possible_poses = self.lemmas[lemma]["pos"]
            if not any(pos in tag for pos in possible_poses):
                return False

        if interpretation == "canonical":
            return True
        if "plural" in interpretation and "Number=Plur" not in tag:
            return False
        if "singular" in interpretation and "Number=Sing" not in tag:
            return False
        if "nominative" not in interpretation and "Case=Nom" in tag:
            return False
        if "genitive" not in interpretation and "Case=Gen" in tag:
            return False
        if "dative" not in interpretation and "Case=Dat" in tag:
            return False
        if "accusative" not in interpretation and "Case=Acc" in tag:
            if not ("ADJ" in tag and "Animacy=Inan" in tag):
                return False
        if "instrumental" not in interpretation and "Case=Ins" in tag:
            return False
        if (
            "prepositional" not in interpretation
            and "locative" not in interpretation
            and "Case=Loc" in tag
        ):
            return False
        if ("present" in interpretation or "future" in interpretation) and "Tense=Past" in tag:
            return False
        if ("past" in interpretation or "future" in interpretation) and "Tense=Pres" in tag:
            return False
        return not (
            ("past" in interpretation or "present" in interpretation) and "Tense=Fut" in tag
        )

    @staticmethod
    def derive_single_accentuation(interpretations: list[dict]) -> str | None:
        if not interpretations:
            return None
        result = interpretations[0]["accentuated"]
        if any(item["accentuated"] != result for item in interpretations[1:]):
            return None
        return result

    def accentuate_word(self, word: dict) -> str:
        if "tag" in word and "PROPN" in word["tag"]:
            return word["token"]
        if word["is_punctuation"] or "interpretations" not in word:
            return word["token"]

        result = self.derive_single_accentuation(word["interpretations"])
        if result is not None:
            return result

        compatible = [
            item
            for item in word["interpretations"]
            if self.compatible(item["form"], item["lemma"], word["tag"])
        ]
        result = self.derive_single_accentuation(compatible)
        if result is not None:
            return result

        same_lemma = [item for item in compatible if item["lemma"] == word["lemma"]]
        return self.derive_single_accentuation(same_lemma) or word["token"]

    def tokenize(self, text: str) -> list[dict]:
        result: list[dict] = []
        for token in _nlp()(text):
            if token.pos_ != "PUNCT":
                word: dict = {"token": token.text, "tag": token.tag_}
                interpretations = self.wordforms.get(word["token"])
                if interpretations is None:
                    interpretations = self.wordforms.get(word["token"].lower())
                if interpretations is not None:
                    word["interpretations"] = interpretations
                word["lemma"] = token.lemma_
                word["is_punctuation"] = False
                word["uppercase"] = word["token"].upper() == word["token"]
                word["starts_with_a_capital_letter"] = word["token"][0].isupper()
            else:
                word = {"token": token.text, "is_punctuation": True}
            word["whitespace"] = token.whitespace_
            result.append(word)
        return result

    def accentuate(self, text: str) -> str:
        result = ""
        for word in self.tokenize(text):
            accentuated = self.accentuate_word(word)
            if word.get("starts_with_a_capital_letter"):
                accentuated = accentuated.capitalize()
            if word.get("uppercase"):
                accentuated = accentuated.upper()
            result += accentuated + word["whitespace"]
        return result

    def __str__(self) -> str:
        # All bot messages use Telegram HTML parse mode. Escape user-controlled
        # text after accentuation so inputs such as "<b>" cannot become markup.
        return render_telegram_html(self.accentuate(self.text))

    def __repr__(self) -> str:
        return str(self)
