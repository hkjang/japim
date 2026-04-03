from __future__ import annotations

import hashlib
import re


HYPHEN_TRANSLATION = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "―": "-",
        "·": ".",
        "•": ".",
        "∙": ".",
        "‧": ".",
        "：": ":",
    }
)


def normalize_ocr_text(value: str) -> str:
    value = value.translate(HYPHEN_TRANSLATION)
    value = re.sub(r"(?<=\w)\s*([@._:/-])\s*(?=\w)", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def masked_preview(text: str, spans: list[tuple[int, int]], mask_char: str = "*") -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(max(0, start), min(len(chars), end)):
            if not chars[index].isspace():
                chars[index] = mask_char
    return "".join(chars)


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
