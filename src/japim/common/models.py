from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


Point = tuple[float, float]
Polygon = list[Point]
Rect = tuple[float, float, float, float]


@dataclass(slots=True)
class OCRToken:
    token_id: str
    page_no: int
    text: str
    confidence: float
    polygon: Polygon

    @property
    def rect(self) -> Rect:
        xs = [point[0] for point in self.polygon]
        ys = [point[1] for point in self.polygon]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        left, _, right, _ = self.rect
        return max(0.0, right - left)

    @property
    def center_y(self) -> float:
        _, top, _, bottom = self.rect
        return (top + bottom) / 2

    @property
    def left(self) -> float:
        left, _, _, _ = self.rect
        return left

    @property
    def right(self) -> float:
        _, _, right, _ = self.rect
        return right


@dataclass(slots=True)
class TokenSpan:
    token: OCRToken
    start: int
    end: int


@dataclass(slots=True)
class TextLine:
    line_id: str
    page_no: int
    text: str
    token_spans: list[TokenSpan] = field(default_factory=list)


@dataclass(slots=True)
class DetectionCandidate:
    rule_id: str
    pii_type: str
    priority: int
    page_no: int
    line_id: str
    line_text: str
    matched_text: str
    match_span: tuple[int, int]
    mask_spans: list[tuple[int, int]]
    masked_preview: str
    confidence: float


@dataclass(slots=True)
class RuleMatch:
    rule_id: str
    detected_type: str
    page_no: int
    line_id: str
    matched_text_hash: str
    masked_preview: str
    bboxes: list[Rect]
    confidence: float


@dataclass(slots=True)
class RenderedPage:
    page_no: int
    image_path: Path
    width: int
    height: int


@dataclass(slots=True)
class PageProcessResult:
    page_no: int
    status: str
    masked_image_path: Path
    detections: list[RuleMatch] = field(default_factory=list)
    ocr_json_path: Path | None = None
    debug_image_path: Path | None = None
    error_message: str | None = None
    processing_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["masked_image_path"] = str(self.masked_image_path)
        if self.ocr_json_path is not None:
            payload["ocr_json_path"] = str(self.ocr_json_path)
        if self.debug_image_path is not None:
            payload["debug_image_path"] = str(self.debug_image_path)
        return payload


@dataclass(slots=True)
class PdfMetadata:
    input_file: Path
    page_count: int
    file_size: int
    is_encrypted: bool


@dataclass(slots=True)
class JobResult:
    job_id: str
    input_file: Path
    output_dir: Path
    masked_pdf_path: Path
    page_results: list[PageProcessResult]

    @property
    def success_pages(self) -> int:
        return sum(1 for page in self.page_results if page.status == "success")

    @property
    def failed_pages(self) -> int:
        return sum(1 for page in self.page_results if page.status == "fail")
