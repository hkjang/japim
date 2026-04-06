from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from japim.audit.logger import AuditLogger
from japim.common.config import AppConfig
from japim.common.logging_utils import configure_logging
from japim.common.models import JobResult, PageProcessResult, RuleMatch
from japim.common.text import hash_text
from japim.masking.bbox import map_mask_spans_to_rects
from japim.masking.masker import ImageMasker
from japim.ocr.engine import OCREngine
from japim.pdf.assembler import PDFAssembler
from japim.pdf.loader import PDFLoader
from japim.pdf.renderer import PDFRenderer
from japim.postprocess.line_builder import LineBuilder
from japim.preprocess.image_preprocessor import ImagePreprocessor
from japim.rules.registry import RuleRegistry


class PIIMaskingPipeline:
    def __init__(self, config: AppConfig, verbose: bool = False) -> None:
        self.config = config
        self.config.ensure_directories()

        self.loader = PDFLoader()
        self.renderer = PDFRenderer(dpi=config.dpi)
        self.preprocessor = ImagePreprocessor(
            enable_grayscale=config.enable_grayscale,
            enable_binarize=config.enable_binarize,
            enable_denoise=config.enable_denoise,
            enable_deskew=config.enable_deskew,
            min_short_edge=config.min_short_edge,
        )
        self.ocr_engine = OCREngine(
            backend=config.ocr_backend,
            lang=config.ocr_lang,
            use_angle_cls=config.use_angle_cls,
            confidence_threshold=config.confidence_threshold,
            use_gpu=config.paddle.use_gpu,
            device=config.paddle.device,
            mock_ocr_dir=config.mock_ocr_dir,
            det_model_dir=config.paddle.det_model_dir,
            rec_model_dir=config.paddle.rec_model_dir,
            cls_model_dir=config.paddle.cls_model_dir,
            text_detection_model_name=config.paddle.text_detection_model_name,
            text_recognition_model_name=config.paddle.text_recognition_model_name,
            textline_orientation_model_name=config.paddle.textline_orientation_model_name,
            text_det_limit_side_len=config.paddle.text_det_limit_side_len,
            text_det_limit_type=config.paddle.text_det_limit_type,
            textline_orientation_batch_size=config.paddle.textline_orientation_batch_size,
            text_recognition_batch_size=config.paddle.text_recognition_batch_size,
            gpu_allocator_strategy=config.paddle.gpu_allocator_strategy,
            fraction_of_gpu_memory_to_use=config.paddle.fraction_of_gpu_memory_to_use,
            show_log=config.paddle.show_log,
        )
        self.line_builder = LineBuilder(
            line_merge_tolerance_px=config.line_merge_tolerance_px,
            token_gap_multiplier=config.token_gap_multiplier,
        )
        self.rule_registry = RuleRegistry(config.enabled_rules)
        self.masker = ImageMasker(
            style=config.mask_style,
            color=config.mask_color,
            blur_radius=config.blur_radius,
            pixelate_block_size=config.pixelate_block_size,
        )
        self.assembler = PDFAssembler()
        self.logger = configure_logging(verbose=verbose)

    def run(self, input_file: str | Path, selected_pages: set[int] | None = None) -> JobResult:
        input_path = Path(input_file)
        metadata = self.loader.inspect(input_path)

        job_id = f"{self.config.job_name_prefix}-{uuid.uuid4().hex[:12]}"
        job_dir = self.config.output_dir / job_id
        rendered_dir = job_dir / "rendered"
        preprocessed_dir = job_dir / "preprocessed"
        masked_dir = job_dir / "masked"
        ocr_dir = job_dir / "ocr"
        debug_dir = job_dir / "debug"
        for directory in (rendered_dir, preprocessed_dir, masked_dir, ocr_dir, debug_dir):
            directory.mkdir(parents=True, exist_ok=True)

        audit = AuditLogger(
            job_dir=job_dir,
            write_csv=self.config.audit.write_csv,
            write_jsonl=self.config.audit.write_jsonl,
            write_summary=self.config.audit.write_summary,
        )

        self.logger.info("Rendering PDF pages: %s", metadata.input_file)
        rendered_pages = self.renderer.render(input_path, rendered_dir, selected_pages=selected_pages)
        page_results: list[PageProcessResult] = []

        for rendered_page in rendered_pages:
            started = time.perf_counter()
            masked_image_path = masked_dir / rendered_page.image_path.name
            ocr_json_path = ocr_dir / f"page_{rendered_page.page_no:04d}.json"
            debug_image_path = debug_dir / rendered_page.image_path.name

            try:
                preprocessed_path = preprocessed_dir / rendered_page.image_path.name
                self.preprocessor.process(rendered_page.image_path, preprocessed_path)
                tokens = self.ocr_engine.recognize(preprocessed_path, rendered_page.page_no)

                if self.config.save_ocr_json:
                    self._write_ocr_json(tokens, ocr_json_path)

                if not tokens:
                    shutil.copy2(rendered_page.image_path, masked_image_path)
                    result = PageProcessResult(
                        page_no=rendered_page.page_no,
                        status="skip",
                        masked_image_path=masked_image_path,
                        ocr_json_path=ocr_json_path if self.config.save_ocr_json else None,
                        error_message="no_text",
                        processing_time_ms=int((time.perf_counter() - started) * 1000),
                    )
                    page_results.append(result)
                    audit.record_page(result)
                    continue

                lines = self.line_builder.build(tokens, rendered_page.page_no)
                candidates = self.rule_registry.detect(lines)
                line_index = {line.line_id: line for line in lines}

                matches: list[RuleMatch] = []
                for candidate in candidates:
                    line = line_index[candidate.line_id]
                    rects = map_mask_spans_to_rects(line, candidate.mask_spans, self.config.mask_padding)
                    if not rects:
                        continue
                    matches.append(
                        RuleMatch(
                            rule_id=candidate.rule_id,
                            detected_type=candidate.pii_type,
                            page_no=candidate.page_no,
                            line_id=candidate.line_id,
                            matched_text_hash=hash_text(candidate.matched_text),
                            masked_preview=candidate.masked_preview,
                            bboxes=rects,
                            confidence=candidate.confidence,
                        )
                    )

                self.masker.apply(rendered_page.image_path, masked_image_path, matches)
                debug_output = None
                if self.config.save_debug_image:
                    debug_output = self.masker.create_debug_overlay(rendered_page.image_path, debug_image_path, matches)

                result = PageProcessResult(
                    page_no=rendered_page.page_no,
                    status="success",
                    masked_image_path=masked_image_path,
                    detections=matches,
                    ocr_json_path=ocr_json_path if self.config.save_ocr_json else None,
                    debug_image_path=debug_output,
                    processing_time_ms=int((time.perf_counter() - started) * 1000),
                )
                page_results.append(result)
                audit.record_page(result)
            except Exception as exc:
                self.logger.exception("Failed to process page %s", rendered_page.page_no)
                shutil.copy2(rendered_page.image_path, masked_image_path)
                result = PageProcessResult(
                    page_no=rendered_page.page_no,
                    status="fail",
                    masked_image_path=masked_image_path,
                    error_message=str(exc),
                    processing_time_ms=int((time.perf_counter() - started) * 1000),
                )
                page_results.append(result)
                audit.record_page(result)
                if self.config.stop_on_error:
                    break

        final_pdf = job_dir / f"{input_path.stem}.masked.pdf"
        masked_images = [result.masked_image_path for result in sorted(page_results, key=lambda item: item.page_no)]
        self.assembler.assemble(masked_images, final_pdf)

        job_result = JobResult(
            job_id=job_id,
            input_file=input_path,
            output_dir=job_dir,
            masked_pdf_path=final_pdf,
            page_results=page_results,
        )
        audit.finalize(job_result)
        return job_result

    def _write_ocr_json(self, tokens, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "token_id": token.token_id,
                "page_no": token.page_no,
                "text": token.text,
                "confidence": token.confidence,
                "polygon": token.polygon,
            }
            for token in tokens
        ]
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
