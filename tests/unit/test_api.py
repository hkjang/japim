import json
import time
from pathlib import Path
from urllib.parse import quote

import fitz
import yaml
from fastapi.testclient import TestClient

from japim.api.app import create_app


def test_health_endpoint():
    client = TestClient(create_app("configs/default.yaml"))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_rejects_non_pdf():
    client = TestClient(create_app("configs/default.yaml"))
    response = client.post(
        "/api/v1/jobs",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400


def test_download_preserves_korean_filename(tmp_path: Path):
    sample_pdf = tmp_path / "샘플 문서.pdf"
    mock_dir = tmp_path / "mock_ocr"
    mock_dir.mkdir()

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 120), "MOBILE 010-1234-5678", fontsize=28, fontname="helv")
    document.save(sample_pdf)
    document.close()

    (mock_dir / "page_0001.json").write_text(
        json.dumps(
            [
                {
                    "text": "MOBILE 010-1234-5678",
                    "confidence": 0.99,
                    "polygon": [[72, 92], [420, 92], [420, 128], [72, 128]],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "job_name_prefix": "api-unit",
                "output_dir": str(tmp_path / "output"),
                "temp_dir": str(tmp_path / "temp"),
                "ocr_backend": "mock",
                "mock_ocr_dir": str(mock_dir),
                "enabled_rules": ["RULE-05"],
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
            files={"file": ("샘플 문서.pdf", handle.read(), "application/pdf")},
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
    assert pdf_response.status_code == 200
    content_disposition = pdf_response.headers["content-disposition"]
    assert quote("샘플 문서.masked.pdf") in content_disposition


def test_job_reports_fail_when_page_processing_fails(tmp_path: Path):
    sample_pdf = tmp_path / "broken.pdf"
    mock_dir = tmp_path / "mock_ocr"
    mock_dir.mkdir()

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 120), "MOBILE 010-1234-5678", fontsize=28, fontname="helv")
    document.save(sample_pdf)
    document.close()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "job_name_prefix": "api-unit",
                "output_dir": str(tmp_path / "output"),
                "temp_dir": str(tmp_path / "temp"),
                "ocr_backend": "mock",
                "mock_ocr_dir": str(mock_dir),
                "enabled_rules": ["RULE-05"],
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
            files={"file": ("broken.pdf", handle.read(), "application/pdf")},
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
    assert status_payload["status"] == "fail"
    assert status_payload["page_successes"] == 0
    assert status_payload["page_failures"] == 1
    assert "1 page(s) failed" in status_payload["message"]
    assert status_payload["masked_pdf_url"] is not None
