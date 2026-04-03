from __future__ import annotations

import csv
import json
from pathlib import Path

from japim.common.models import JobResult, PageProcessResult


class AuditLogger:
    def __init__(self, job_dir: Path, write_csv: bool, write_jsonl: bool, write_summary: bool) -> None:
        self.job_dir = job_dir
        self.write_csv = write_csv
        self.write_jsonl = write_jsonl
        self.write_summary = write_summary
        self.records: list[dict] = []
        self.log_dir = job_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def record_page(self, page_result: PageProcessResult) -> None:
        for detection in page_result.detections:
            self.records.append(
                {
                    "page_no": page_result.page_no,
                    "rule_id": detection.rule_id,
                    "detected_type": detection.detected_type,
                    "masked_preview": detection.masked_preview,
                    "bbox": json.dumps(detection.bboxes, ensure_ascii=False),
                    "confidence": detection.confidence,
                    "status": page_result.status,
                    "error_message": page_result.error_message or "",
                    "processing_time_ms": page_result.processing_time_ms,
                    "matched_text_hash": detection.matched_text_hash,
                }
            )

        if not page_result.detections:
            self.records.append(
                {
                    "page_no": page_result.page_no,
                    "rule_id": "",
                    "detected_type": "",
                    "masked_preview": "",
                    "bbox": "[]",
                    "confidence": 0.0,
                    "status": page_result.status,
                    "error_message": page_result.error_message or "",
                    "processing_time_ms": page_result.processing_time_ms,
                    "matched_text_hash": "",
                }
            )

    def finalize(self, job_result: JobResult) -> None:
        if self.write_jsonl:
            jsonl_path = self.log_dir / "detections.jsonl"
            with jsonl_path.open("w", encoding="utf-8") as handle:
                for record in self.records:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        if self.write_csv:
            csv_path = self.log_dir / "detections.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "page_no",
                        "rule_id",
                        "detected_type",
                        "masked_preview",
                        "bbox",
                        "confidence",
                        "status",
                        "error_message",
                        "processing_time_ms",
                        "matched_text_hash",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.records)

        if self.write_summary:
            summary = {
                "job_id": job_result.job_id,
                "input_file": str(job_result.input_file),
                "masked_pdf_path": str(job_result.masked_pdf_path),
                "success_pages": job_result.success_pages,
                "failed_pages": job_result.failed_pages,
                "page_results": [page.to_dict() for page in job_result.page_results],
            }
            summary_path = self.log_dir / "job_summary.json"
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
