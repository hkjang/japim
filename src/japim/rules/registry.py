from __future__ import annotations

import re
from typing import Iterable

from japim.common.models import DetectionCandidate, TextLine
from japim.rules.base import RegexRule


class ResidentRegistrationRule(RegexRule):
    rule_id = "RULE-01"
    pii_type = "resident_registration_number"
    priority = 180
    pattern = re.compile(r"(?<!\d)(\d{6})[-.\s]?([1-4]\d{6})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(2), match.end(2))


class DriverLicenseRule(RegexRule):
    rule_id = "RULE-02"
    pii_type = "driver_license_number"
    priority = 160
    pattern = re.compile(r"(?<!\d)(\d{2})[-.\s]?(\d{2})[-.\s]?(\d{6})[-.\s]?(\d{2})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(3), match.end(3))


class PassportRule(RegexRule):
    rule_id = "RULE-03"
    pii_type = "passport_number"
    priority = 130
    pattern = re.compile(r"(?:(?:여권(?:번호)?)\s*[:：]?\s*)?([A-Z]{1,2}\d{7,8}|\d{8,9})", re.IGNORECASE)

    def is_valid(self, line_text: str, match: re.Match[str]) -> bool:
        prefix = line_text[max(0, match.start() - 6) : match.start()]
        return "여권" in prefix or bool(re.fullmatch(r"[A-Z]{1,2}\d{7,8}|\d{8,9}", match.group(1)))

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        end = match.end(1)
        yield (max(match.start(1), end - 4), end)


class ForeignerRegistrationRule(RegexRule):
    rule_id = "RULE-04"
    pii_type = "foreigner_registration_number"
    priority = 185
    pattern = re.compile(r"(?<!\d)(\d{6})[-.\s]?([5-8]\d{6})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(2), match.end(2))


class MobilePhoneRule(RegexRule):
    rule_id = "RULE-05"
    pii_type = "mobile_phone_number"
    priority = 150
    pattern = re.compile(r"(?<!\d)(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(3), match.end(3))


class LandlinePhoneRule(RegexRule):
    rule_id = "RULE-06"
    pii_type = "landline_phone_number"
    priority = 140
    pattern = re.compile(r"(?<!\d)(0(?:2|[3-6][1-5]))[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(3), match.end(3))


class CreditCardRule(RegexRule):
    rule_id = "RULE-07"
    pii_type = "credit_card_number"
    priority = 170
    pattern = re.compile(r"(?<!\d)(\d{4})[-.\s]?(\d{4})[-.\s]?(\d{4})[-.\s]?(\d{4})(?!\d)")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        yield (match.start(1), match.end(1))
        yield (match.start(2), match.end(2))
        yield (match.start(3), match.end(3))


class BankAccountRule(RegexRule):
    rule_id = "RULE-08"
    pii_type = "bank_account_number"
    priority = 120
    pattern = re.compile(r"(?:(?:계좌(?:번호)?|입금계좌|Account)\s*[:：]?\s*)?(\d{2,6}(?:[-.\s]?\d{2,6}){1,4})", re.IGNORECASE)

    def is_valid(self, line_text: str, match: re.Match[str]) -> bool:
        candidate = match.group(1)
        digits = re.sub(r"\D+", "", candidate)
        context = line_text[max(0, match.start() - 12) : match.end() + 2]
        return len(digits) >= 10 and any(keyword in context for keyword in ("계좌", "입금", "은행", "Account"))

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        candidate = match.group(1)
        keep_tail = 5
        digit_positions = [index for index, char in enumerate(candidate) if char.isdigit()]
        if len(digit_positions) <= keep_tail:
            yield (match.start(1), match.end(1))
            return

        masked_digits = digit_positions[:-keep_tail]
        start = None
        last = None
        for position in masked_digits:
            absolute = match.start(1) + position
            if start is None:
                start = absolute
            elif last is not None and absolute != last + 1:
                yield (start, last + 1)
                start = absolute
            last = absolute
        if start is not None and last is not None:
            yield (start, last + 1)


class PersonNameRule(RegexRule):
    rule_id = "RULE-09"
    pii_type = "person_name"
    priority = 90
    pattern = re.compile(r"(성명|이름|고객명|대표자|신청인)\s*[:：]?\s*([가-힣]{2,4})")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        for index in range(match.start(2) + 1, match.end(2), 2):
            yield (index, index + 1)


class EmailRule(RegexRule):
    rule_id = "RULE-10"
    pii_type = "email"
    priority = 135
    pattern = re.compile(r"([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        local = match.group(1)
        local_start = match.start(1)
        if len(local) <= 4:
            yield (local_start, match.end(1))
            return
        yield (local_start + 3, match.end(1))


class IPv4Rule(RegexRule):
    rule_id = "RULE-11"
    pii_type = "ipv4"
    priority = 110
    pattern = re.compile(r"(?<!\d)((?:\d{1,3}\.){3}\d{1,3})(?!\d)")

    def is_valid(self, line_text: str, match: re.Match[str]) -> bool:
        octets = match.group(1).split(".")
        return all(0 <= int(octet) <= 255 for octet in octets)

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        ip = match.group(1)
        last_octet = ip.split(".")[-1]
        yield (match.end(1) - len(last_octet), match.end(1))


class AddressRule(RegexRule):
    rule_id = "RULE-12"
    pii_type = "address"
    priority = 80
    pattern = re.compile(r"(주소|소재지|거주지)\s*[:：]?\s*([^\n]{6,120})")

    def is_valid(self, line_text: str, match: re.Match[str]) -> bool:
        candidate = match.group(2)
        return any(keyword in candidate for keyword in ("로", "길", "동", "읍", "면", "리", "번지", "아파트"))

    def build_mask_spans(self, match: re.Match[str]) -> Iterable[tuple[int, int]]:
        address = match.group(2)
        tokens = address.split()
        if len(tokens) <= 2:
            midpoint = max(1, len(address) // 2)
            yield (match.start(2) + midpoint, match.end(2))
            return
        keep_text = " ".join(tokens[:2])
        yield (match.start(2) + len(keep_text), match.end(2))


class RuleRegistry:
    def __init__(self, enabled_rules: list[str] | None = None) -> None:
        rules = [
            ResidentRegistrationRule(),
            DriverLicenseRule(),
            PassportRule(),
            ForeignerRegistrationRule(),
            MobilePhoneRule(),
            LandlinePhoneRule(),
            CreditCardRule(),
            BankAccountRule(),
            PersonNameRule(),
            EmailRule(),
            IPv4Rule(),
            AddressRule(),
        ]
        enabled = set(enabled_rules or [rule.rule_id for rule in rules])
        self.rules = [rule for rule in rules if rule.rule_id in enabled]

    def detect(self, lines: list[TextLine]) -> list[DetectionCandidate]:
        raw: list[DetectionCandidate] = []
        for line in lines:
            for rule in self.rules:
                raw.extend(rule.detect(line))

        raw.sort(key=lambda item: (item.page_no, item.line_id, -item.priority, item.match_span[0]))

        accepted: list[DetectionCandidate] = []
        occupied: dict[str, list[tuple[int, int]]] = {}
        for candidate in raw:
            existing_spans = occupied.setdefault(candidate.line_id, [])
            if any(_overlap(span, existing) for span in candidate.mask_spans for existing in existing_spans):
                continue

            accepted.append(candidate)
            existing_spans.extend(candidate.mask_spans)

        return accepted


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])
