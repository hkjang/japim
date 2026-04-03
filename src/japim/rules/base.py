from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Iterable

from japim.common.models import DetectionCandidate, TextLine
from japim.common.text import masked_preview


class BaseRule(ABC):
    rule_id: str
    pii_type: str
    priority: int = 100

    @abstractmethod
    def detect(self, line: TextLine) -> list[DetectionCandidate]:
        raise NotImplementedError


class RegexRule(BaseRule):
    pattern: re.Pattern[str]

    def detect(self, line: TextLine) -> list[DetectionCandidate]:
        candidates: list[DetectionCandidate] = []
        for match in self.pattern.finditer(line.text):
            if not self.is_valid(line.text, match):
                continue

            mask_spans = list(self.build_mask_spans(match))
            if not mask_spans:
                continue

            candidates.append(
                DetectionCandidate(
                    rule_id=self.rule_id,
                    pii_type=self.pii_type,
                    priority=self.priority,
                    page_no=line.page_no,
                    line_id=line.line_id,
                    line_text=line.text,
                    matched_text=match.group(0),
                    match_span=(match.start(), match.end()),
                    mask_spans=mask_spans,
                    masked_preview=masked_preview(line.text, mask_spans),
                    confidence=self.estimate_confidence(line.text, match),
                )
            )
        return candidates

    def is_valid(self, line_text: str, match: re.Match[str]) -> bool:
        return True

    def estimate_confidence(self, line_text: str, match: re.Match[str]) -> float:
        return 1.0

    @abstractmethod
    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        raise NotImplementedError
