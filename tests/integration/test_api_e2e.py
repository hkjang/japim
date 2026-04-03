from __future__ import annotations

import json
import time
from pathlib import Path

import fitz
import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from japim.api.app import create_app


def test_api_e2e_with_generated_sample_pdf(tmp_path: Path):
    sample_pdf = tmp_path / "sample.pdf"
    mock_ocr_dir = tmp_path / "mock_ocr"
    mock_ocr_dir.mkdir()

    _generate_sample_pdf(sample_pdf)
    _generate_mock_ocr(mock_ocr_dir / "page_0001.json")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "job_name_prefix": "e2e",
                "output_dir": str(tmp_path / "output"),
                "temp_dir": str(tmp_path / "temp"),
                "ocr_backend": "mock",
                "mock_ocr_dir": str(mock_ocr_dir),
                "save_debug_image": True,
                "save_ocr_json": True,
                "enabled_rules": ["RULE-05", "RULE-10"],
                "paddle": {"use_gpu": False, "device": "cpu"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app(str(config_path)))
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/v1/jobs",
            files={"file": ("sample.pdf", handle.read(), "application/pdf")},
        )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    status_payload = None
    for _ in range(20):
        status_response = client.get(f"/api/v1/jobs/{job_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["status"] in {"success", "fail"}:
            break
        time.sleep(0.1)

    assert status_payload is not None
    assert status_payload["status"] == "success"
    assert status_payload["masked_pdf_url"]
    assert status_payload["detections_csv_url"]

    pdf_response = client.get(status_payload["masked_pdf_url"])
    csv_response = client.get(status_payload["detections_csv_url"])
    jsonl_response = client.get(status_payload["detections_jsonl_url"])

    assert pdf_response.status_code == 200
    assert csv_response.status_code == 200
    assert jsonl_response.status_code == 200
    assert len(pdf_response.content) > 0
    assert "RULE-05" in csv_response.text
    assert "RULE-10" in csv_response.text


def test_api_e2e_with_korean_document_and_filename(tmp_path: Path):
    font_path = _resolve_korean_font()
    if font_path is None:
        pytest.skip("Korean-capable font is not available on this host")

    sample_pdf = tmp_path / "한글 샘플 문서.pdf"
    mock_ocr_dir = tmp_path / "mock_ocr"
    mock_ocr_dir.mkdir()

    _generate_korean_sample_pdf(sample_pdf, font_path)
    _generate_korean_mock_ocr(mock_ocr_dir / "page_0001.json")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "job_name_prefix": "e2e-ko",
                "output_dir": str(tmp_path / "output"),
                "temp_dir": str(tmp_path / "temp"),
                "ocr_backend": "mock",
                "mock_ocr_dir": str(mock_ocr_dir),
                "save_debug_image": True,
                "save_ocr_json": True,
                "enabled_rules": ["RULE-05", "RULE-10"],
                "paddle": {"use_gpu": False, "device": "cpu"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app(str(config_path)))
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/v1/jobs",
            files={"file": ("한글 샘플 문서.pdf", handle.read(), "application/pdf")},
        )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    status_payload = None
    for _ in range(20):
        status_response = client.get(f"/api/v1/jobs/{job_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["status"] in {"success", "fail"}:
            break
        time.sleep(0.1)

    assert status_payload is not None
    assert status_payload["status"] == "success"

    pdf_response = client.get(status_payload["masked_pdf_url"])
    csv_response = client.get(status_payload["detections_csv_url"])

    assert pdf_response.status_code == 200
    assert csv_response.status_code == 200
    assert "RULE-05" in csv_response.text
    assert "RULE-10" in csv_response.text
    assert "utf-8''%ED%95%9C%EA%B8%80%20%EC%83%98%ED%94%8C%20%EB%AC%B8%EC%84%9C.masked.pdf" in pdf_response.headers["content-disposition"]


def _generate_sample_pdf(target_path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 120), "MOBILE 010-1234-5678", fontsize=28, fontname="helv")
    page.insert_text((72, 180), "EMAIL abcdef@example.com", fontsize=28, fontname="helv")
    document.save(target_path)
    document.close()


def _generate_korean_sample_pdf(target_path: Path, font_path: Path) -> None:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), size=48)
    draw.text((72, 120), "휴대폰 010-1234-5678", fill="black", font=font)
    draw.text((72, 240), "이메일 abcdef@example.com", fill="black", font=font)

    buffer = image_to_png_bytes(image)
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(0, 0, 595, 842), stream=buffer)
    document.save(target_path)
    document.close()


def _generate_mock_ocr(target_path: Path) -> None:
    payload = [
        {
            "text": "MOBILE 010-1234-5678",
            "confidence": 0.99,
            "polygon": [[72, 92], [420, 92], [420, 128], [72, 128]],
        },
        {
            "text": "EMAIL abcdef@example.com",
            "confidence": 0.99,
            "polygon": [[72, 152], [470, 152], [470, 188], [72, 188]],
        }
    ]
    target_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _generate_korean_mock_ocr(target_path: Path) -> None:
    payload = [
        {
            "text": "휴대폰 010-1234-5678",
            "confidence": 0.99,
            "polygon": [[72, 120], [620, 120], [620, 172], [72, 172]],
        },
        {
            "text": "이메일 abcdef@example.com",
            "confidence": 0.99,
            "polygon": [[72, 240], [760, 240], [760, 292], [72, 292]],
        },
    ]
    target_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _resolve_korean_font() -> Path | None:
    candidates = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def image_to_png_bytes(image: Image.Image) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
