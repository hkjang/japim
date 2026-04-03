from japim.common.models import OCRToken, TextLine, TokenSpan
from japim.masking.bbox import map_mask_spans_to_rects


def make_token(token_id: str, text: str, left: float, top: float, right: float, bottom: float) -> OCRToken:
    return OCRToken(
        token_id=token_id,
        page_no=1,
        text=text,
        confidence=0.99,
        polygon=[(left, top), (right, top), (right, bottom), (left, bottom)],
    )


def test_partial_mask_span_maps_to_partial_rect():
    token = make_token("t1", "01012345678", 0, 0, 110, 20)
    line = TextLine(
        line_id="line-1",
        page_no=1,
        text="01012345678",
        token_spans=[TokenSpan(token=token, start=0, end=11)],
    )

    rects = map_mask_spans_to_rects(line, [(7, 11)], padding=0)

    assert len(rects) == 1
    left, _, right, _ = rects[0]
    assert left >= 69
    assert right <= 111
