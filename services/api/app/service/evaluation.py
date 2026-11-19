"""Deterministic evaluation of a transcript against its script. Pure, no I/O.

Word error rate is the word-level Levenshtein distance (substitutions,
deletions, insertions) divided by the number of reference words, after the
same normalization on both sides. Expected phrases are matched as normalized
substrings of the transcript. Normalization maps number words to digits
("ten" -> "10", "twenty five" -> "25") so a script written in words and an ASR
transcript written in digits compare equal.
"""

import re

_NON_WORD = re.compile(r"[^a-z0-9' ]+")
_SPACES = re.compile(r"\s+")

_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_UNIT_VALUES = {word: n for n, word in enumerate(_UNITS)}
_TENS_VALUES = {word: 10 * n for n, word in enumerate(_TENS, start=2)}


def _numbers_to_digits(words: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in _TENS_VALUES:
            value = _TENS_VALUES[word]
            nxt = words[i + 1] if i + 1 < len(words) else ""
            if 0 < _UNIT_VALUES.get(nxt, 0) < 10:
                value += _UNIT_VALUES[nxt]
                i += 1
            out.append(str(value))
        elif word in _UNIT_VALUES:
            out.append(str(_UNIT_VALUES[word]))
        else:
            out.append(word)
        i += 1
    return out


def normalize(text: str) -> str:
    lowered = text.lower().replace("-", " ")
    words = _SPACES.sub(" ", _NON_WORD.sub(" ", lowered)).split()
    return " ".join(_numbers_to_digits(words))


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = normalize(reference).split()
    hyp = normalize(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i] + [0] * len(hyp)
        for j, hyp_word in enumerate(hyp, start=1):
            cost = 0 if ref_word == hyp_word else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
        previous = current
    return round(previous[-1] / len(ref), 4)


def phrase_coverage(transcript: str, phrases: list[str]) -> tuple[list[str], list[str]]:
    """Split expected phrases into (found, missing)."""
    haystack = f" {normalize(transcript)} "
    found = [p for p in phrases if f" {normalize(p)} " in haystack]
    missing = [p for p in phrases if p not in found]
    return found, missing


def evaluate(reference: str, hypothesis: str, phrases: list[str], max_wer: float) -> dict:
    wer = word_error_rate(reference, hypothesis)
    found, missing = phrase_coverage(hypothesis, phrases)
    return {
        "wer": wer,
        "max_wer": max_wer,
        "phrases_found": found,
        "phrases_missing": missing,
        "passed": wer <= max_wer and not missing,
    }
