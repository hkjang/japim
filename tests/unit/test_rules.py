from japim.common.models import TextLine
from japim.rules.registry import RuleRegistry


def test_email_rule_masks_local_part_after_first_three_characters():
    line = TextLine(line_id="l1", page_no=1, text="이메일: abcdef@example.com", token_spans=[])
    registry = RuleRegistry(enabled_rules=["RULE-10"])
    results = registry.detect([line])

    assert len(results) == 1
    assert results[0].mask_spans == [(8, 11)]


def test_resident_rule_masks_back_seven_digits():
    line = TextLine(line_id="l1", page_no=1, text="주민번호 900101-1234567", token_spans=[])
    registry = RuleRegistry(enabled_rules=["RULE-01"])
    results = registry.detect([line])

    assert len(results) == 1
    start, end = results[0].mask_spans[0]
    assert line.text[start:end] == "1234567"
