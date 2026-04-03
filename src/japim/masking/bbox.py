from __future__ import annotations

from japim.common.models import Rect, TextLine, TokenSpan


def expand_rect(rect: Rect, padding: int) -> Rect:
    left, top, right, bottom = rect
    return (
        max(0.0, left - padding),
        max(0.0, top - padding),
        right + padding,
        bottom + padding,
    )


def overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return not (end_a <= start_b or end_b <= start_a)


def split_rect_for_span(span: TokenSpan, start: int, end: int) -> Rect:
    left, top, right, bottom = span.token.rect
    token_length = max(1, len(span.token.text))
    span_length = max(1, span.end - span.start)
    width = max(1.0, right - left)
    avg_char_width = width / token_length

    start_offset = max(0, start - span.start)
    end_offset = min(span_length, end - span.start)
    start_x = left + avg_char_width * start_offset
    end_x = left + avg_char_width * end_offset
    return (start_x, top, end_x, bottom)


def map_mask_spans_to_rects(line: TextLine, mask_spans: list[tuple[int, int]], padding: int) -> list[Rect]:
    rects: list[Rect] = []
    for mask_start, mask_end in mask_spans:
        for span in line.token_spans:
            if not overlap(mask_start, mask_end, span.start, span.end):
                continue

            local_start = max(mask_start, span.start)
            local_end = min(mask_end, span.end)
            if local_start >= local_end:
                continue

            rects.append(expand_rect(split_rect_for_span(span, local_start, local_end), padding))

    return merge_rects(rects)


def merge_rects(rects: list[Rect], margin: float = 2.0) -> list[Rect]:
    merged: list[Rect] = []
    for rect in rects:
        current = rect
        updated = True
        while updated:
            updated = False
            next_merged: list[Rect] = []
            for candidate in merged:
                if _touching(current, candidate, margin):
                    current = (
                        min(current[0], candidate[0]),
                        min(current[1], candidate[1]),
                        max(current[2], candidate[2]),
                        max(current[3], candidate[3]),
                    )
                    updated = True
                else:
                    next_merged.append(candidate)
            merged = next_merged
        merged.append(current)
    return merged


def _touching(a: Rect, b: Rect, margin: float) -> bool:
    return not (
        a[2] < b[0] - margin
        or b[2] < a[0] - margin
        or a[3] < b[1] - margin
        or b[3] < a[1] - margin
    )
