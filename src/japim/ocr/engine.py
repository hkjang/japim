from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any

import yaml

from japim.common.models import OCRToken


logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(
        self,
        backend: str,
        lang: str,
        use_angle_cls: bool,
        confidence_threshold: float,
        use_gpu: bool,
        device: str,
        mock_ocr_dir: Path | None = None,
        det_model_dir: Path | None = None,
        rec_model_dir: Path | None = None,
        cls_model_dir: Path | None = None,
        show_log: bool = False,
    ) -> None:
        self.backend = backend
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.device = device
        self.mock_ocr_dir = mock_ocr_dir
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self.cls_model_dir = cls_model_dir
        self.show_log = show_log
        self._ocr = None

    def _get_engine(self):
        if self._ocr is not None:
            return self._ocr

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("paddleocr is not installed") from exc

        parameters = set(inspect.signature(PaddleOCR).parameters)
        runtime_device = self.device if self.use_gpu else "cpu"

        if "use_doc_orientation_classify" in parameters:
            kwargs: dict[str, Any] = {
                "lang": self.lang,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": self.use_angle_cls,
                "device": runtime_device,
            }
            if "ocr_version" in parameters and not any((self.det_model_dir, self.rec_model_dir, self.cls_model_dir)):
                kwargs["ocr_version"] = "PP-OCRv5"
            if self.det_model_dir:
                model_name = self._read_model_name(self.det_model_dir)
                if model_name and "text_detection_model_name" in parameters:
                    kwargs["text_detection_model_name"] = model_name
                kwargs["text_detection_model_dir"] = str(self.det_model_dir)
            if self.rec_model_dir:
                model_name = self._read_model_name(self.rec_model_dir)
                if model_name and "text_recognition_model_name" in parameters:
                    kwargs["text_recognition_model_name"] = model_name
                kwargs["text_recognition_model_dir"] = str(self.rec_model_dir)
            if self.cls_model_dir:
                model_name = self._read_model_name(self.cls_model_dir)
                if model_name and "textline_orientation_model_name" in parameters:
                    kwargs["textline_orientation_model_name"] = model_name
                kwargs["textline_orientation_model_dir"] = str(self.cls_model_dir)
            if "show_log" in parameters:
                kwargs["show_log"] = self.show_log
        else:
            kwargs = {
                "lang": self.lang,
                "use_angle_cls": self.use_angle_cls,
                "use_gpu": self.use_gpu,
                "device": runtime_device,
                "show_log": self.show_log,
            }
            if self.det_model_dir:
                kwargs["det_model_dir"] = str(self.det_model_dir)
            if self.rec_model_dir:
                kwargs["rec_model_dir"] = str(self.rec_model_dir)
            if self.cls_model_dir:
                kwargs["cls_model_dir"] = str(self.cls_model_dir)

        self._ocr = PaddleOCR(**kwargs)
        return self._ocr

    def recognize(self, image_path: str | Path, page_no: int) -> list[OCRToken]:
        if self.backend == "mock":
            return self._recognize_mock(page_no)

        try:
            return self._recognize_with_backend(image_path, page_no)
        except Exception as exc:
            if self._should_fallback_to_cpu(exc):
                return self._fallback_recognize_cpu(image_path, page_no, exc)
            raise

    def _recognize_with_backend(self, image_path: str | Path, page_no: int) -> list[OCRToken]:
        engine = self._get_engine()
        if hasattr(engine, "predict"):
            raw_result = engine.predict(str(image_path))
            return self._parse_predict_results(raw_result, page_no)

        raw_result = engine.ocr(str(image_path), cls=self.use_angle_cls)
        return self._parse_legacy_results(raw_result, page_no)

    def _should_fallback_to_cpu(self, exc: Exception) -> bool:
        if not self.use_gpu:
            return False

        message = str(exc).lower()
        markers = (
            "unsupported gpu architecture",
            "mismatched gpu architecture",
            "libcuda.so.1",
            "cuda driver version is insufficient",
            "cannot find cuda",
            "not compiled with cuda",
        )
        return any(marker in message for marker in markers)

    def _fallback_recognize_cpu(self, image_path: str | Path, page_no: int, exc: Exception) -> list[OCRToken]:
        logger.warning("GPU OCR backend initialization failed, falling back to CPU: %s", exc)
        self.use_gpu = False
        self.device = "cpu"
        self._ocr = None
        return self._recognize_with_backend(image_path, page_no)

    def _read_model_name(self, model_dir: Path | None) -> str | None:
        if model_dir is None:
            return None

        inference_yaml = model_dir / "inference.yml"
        if not inference_yaml.exists():
            return None

        try:
            payload = yaml.safe_load(inference_yaml.read_text(encoding="utf-8")) or {}
        except Exception:
            return None

        global_section = payload.get("Global")
        if not isinstance(global_section, dict):
            return None

        model_name = global_section.get("model_name")
        return str(model_name) if model_name else None

    def _parse_predict_results(self, raw_result, page_no: int) -> list[OCRToken]:
        tokens: list[OCRToken] = []
        token_index = 0
        for result in raw_result or []:
            payload = getattr(result, "json", result)
            if not isinstance(payload, dict):
                continue

            data = payload.get("res", payload)
            texts = self._to_list(data.get("rec_texts", []))
            scores = self._to_list(data.get("rec_scores", []))
            polygons = self._to_list(data.get("rec_polys", []))
            boxes = self._to_list(data.get("rec_boxes", []))

            for index, text in enumerate(texts):
                normalized_text = str(text).strip()
                if not normalized_text:
                    continue

                confidence = float(scores[index]) if index < len(scores) else 0.0
                if confidence < self.confidence_threshold:
                    continue

                polygon = self._normalize_polygon(polygons[index] if index < len(polygons) else None)
                if polygon is None and index < len(boxes):
                    polygon = self._box_to_polygon(boxes[index])
                if polygon is None:
                    continue

                tokens.append(
                    OCRToken(
                        token_id=f"p{page_no:04d}_t{token_index:05d}",
                        page_no=page_no,
                        text=normalized_text,
                        confidence=confidence,
                        polygon=polygon,
                    )
                )
                token_index += 1

        return tokens

    def _parse_legacy_results(self, raw_result, page_no: int) -> list[OCRToken]:
        tokens: list[OCRToken] = []
        if not raw_result:
            return tokens

        line_results = raw_result[0] if isinstance(raw_result[0], list) else raw_result
        for index, entry in enumerate(line_results):
            polygon = [(float(point[0]), float(point[1])) for point in entry[0]]
            text = str(entry[1][0]).strip()
            confidence = float(entry[1][1])

            if not text or confidence < self.confidence_threshold:
                continue

            tokens.append(
                OCRToken(
                    token_id=f"p{page_no:04d}_t{index:05d}",
                    page_no=page_no,
                    text=text,
                    confidence=confidence,
                    polygon=polygon,
                )
            )

        return tokens

    def _recognize_mock(self, page_no: int) -> list[OCRToken]:
        if self.mock_ocr_dir is None:
            raise RuntimeError("mock OCR backend requires mock_ocr_dir")

        fixture_path = self.mock_ocr_dir / f"page_{page_no:04d}.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"mock OCR fixture not found: {fixture_path}")

        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        tokens: list[OCRToken] = []
        for index, entry in enumerate(data):
            tokens.append(
                OCRToken(
                    token_id=entry.get("token_id", f"p{page_no:04d}_t{index:05d}"),
                    page_no=page_no,
                    text=str(entry["text"]),
                    confidence=float(entry.get("confidence", 0.99)),
                    polygon=[(float(point[0]), float(point[1])) for point in entry["polygon"]],
                )
            )
        return tokens

    def _to_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            converted = value.tolist()
            return converted if isinstance(converted, list) else [converted]
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _normalize_polygon(self, value: Any) -> list[tuple[float, float]] | None:
        points = self._to_list(value)
        if len(points) < 4:
            return None
        polygon: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return None
            polygon.append((float(point[0]), float(point[1])))
        return polygon

    def _box_to_polygon(self, value: Any) -> list[tuple[float, float]] | None:
        box = self._to_list(value)
        if len(box) < 4:
            return None
        left, top, right, bottom = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        return [(left, top), (right, top), (right, bottom), (left, bottom)]
