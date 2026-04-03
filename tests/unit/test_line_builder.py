from japim.common.models import OCRToken
from japim.postprocess.line_builder import LineBuilder


def token(token_id: str, text: str, left: float, top: float, right: float, bottom: float) -> OCRToken:
    return OCRToken(
        token_id=token_id,
        page_no=1,
        text=text,
        confidence=0.9,
        polygon=[(left, top), (right, top), (right, bottom), (left, bottom)],
    )


def test_line_builder_inserts_space_for_large_gaps():
    builder = LineBuilder(line_merge_tolerance_px=10.0, token_gap_multiplier=0.5)
    lines = builder.build(
        [
            token("t1", "홍길동", 0, 0, 30, 20),
            token("t2", "010-1234-5678", 80, 0, 180, 20),
        ],
        page_no=1,
    )

    assert len(lines) == 1
    assert " " in lines[0].text


def test_line_builder_normalizes_spaces_around_identifier_separators():
    builder = LineBuilder(line_merge_tolerance_px=10.0, token_gap_multiplier=0.5)
    lines = builder.build([token("t1", "abcdef @example.com", 0, 0, 200, 20)], page_no=1)

    assert len(lines) == 1
    assert lines[0].text == "abcdef@example.com"
