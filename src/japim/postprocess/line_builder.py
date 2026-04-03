from __future__ import annotations

from statistics import median

from japim.common.models import OCRToken, TextLine, TokenSpan
from japim.common.text import normalize_ocr_text


class LineBuilder:
    def __init__(self, line_merge_tolerance_px: float, token_gap_multiplier: float) -> None:
        self.line_merge_tolerance_px = line_merge_tolerance_px
        self.token_gap_multiplier = token_gap_multiplier

    def build(self, tokens: list[OCRToken], page_no: int) -> list[TextLine]:
        if not tokens:
            return []

        sorted_tokens = sorted(tokens, key=lambda token: (token.center_y, token.left))
        grouped: list[list[OCRToken]] = []
        for token in sorted_tokens:
            if not grouped:
                grouped.append([token])
                continue

            last_group = grouped[-1]
            avg_center_y = sum(item.center_y for item in last_group) / len(last_group)
            if abs(token.center_y - avg_center_y) <= self.line_merge_tolerance_px:
                last_group.append(token)
            else:
                grouped.append([token])

        lines: list[TextLine] = []
        for index, group in enumerate(grouped, start=1):
            group = sorted(group, key=lambda token: token.left)
            line_text_parts: list[str] = []
            spans: list[TokenSpan] = []
            cursor = 0
            char_width_candidates = [
                token.width / max(len(token.text), 1)
                for token in group
                if token.text and token.width > 0
            ]
            median_char_width = median(char_width_candidates) if char_width_candidates else 8.0
            gap_threshold = median_char_width * self.token_gap_multiplier

            previous_token = None
            for token in group:
                normalized = normalize_ocr_text(token.text)
                if not normalized:
                    continue

                if previous_token is not None:
                    gap = token.left - previous_token.right
                    if gap > gap_threshold:
                        line_text_parts.append(" ")
                        cursor += 1

                start = cursor
                line_text_parts.append(normalized)
                cursor += len(normalized)
                spans.append(TokenSpan(token=token, start=start, end=cursor))
                previous_token = token

            line_text = "".join(line_text_parts).strip()
            if not line_text:
                continue

            offset = 1 if line_text_parts and line_text_parts[0] == " " else 0
            adjusted_spans = [
                TokenSpan(token=span.token, start=span.start - offset, end=span.end - offset)
                for span in spans
            ]
            lines.append(
                TextLine(
                    line_id=f"p{page_no:04d}_l{index:04d}",
                    page_no=page_no,
                    text=line_text,
                    token_spans=adjusted_spans,
                )
            )

        return lines
