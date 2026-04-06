from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from japim.common.config import AppConfig, load_config
from japim.pipeline import PIIMaskingPipeline


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "success", "fail"]
    input_filename: str
    message: str | None = None
    page_successes: int | None = None
    page_failures: int | None = None
    output_dir: str | None = None
    masked_pdf_url: str | None = None
    detections_csv_url: str | None = None
    detections_jsonl_url: str | None = None
    debug_dir_url: str | None = None


@dataclass
class JobState:
    job_id: str
    input_filename: str
    upload_path: Path
    status: str = "queued"
    message: str | None = None
    page_successes: int | None = None
    page_failures: int | None = None
    output_dir: Path | None = None
    masked_pdf_path: Path | None = None
    extra_files: dict[str, Path] = field(default_factory=dict)


class JobManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._jobs: dict[str, JobState] = {}
        self._lock = Lock()

    def create_job(self, upload_path: Path, input_filename: str) -> JobState:
        job_id = uuid.uuid4().hex
        state = JobState(job_id=job_id, input_filename=input_filename, upload_path=upload_path)
        with self._lock:
            self._jobs[job_id] = state
        return state

    def get(self, job_id: str) -> JobState:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id]

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id].status = "running"

    def mark_completed(
        self,
        job_id: str,
        output_dir: Path,
        masked_pdf: Path,
        page_successes: int,
        page_failures: int,
    ) -> None:
        logs_dir = output_dir / "logs"
        with self._lock:
            job = self._jobs[job_id]
            job.status = "fail" if page_failures else "success"
            job.message = f"{page_failures} page(s) failed during OCR or masking" if page_failures else None
            job.page_successes = page_successes
            job.page_failures = page_failures
            job.output_dir = output_dir
            job.masked_pdf_path = masked_pdf
            job.extra_files = {
                "detections_csv": logs_dir / "detections.csv",
                "detections_jsonl": logs_dir / "detections.jsonl",
                "job_summary": logs_dir / "job_summary.json",
                "debug_dir": output_dir / "debug",
            }

    def mark_fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "fail"
            job.message = message


def create_app(config_path: str = "configs/default.yaml") -> FastAPI:
    config = load_config(config_path)
    config.ensure_directories()
    app = FastAPI(title="JAPIM API", version="0.1.0")
    manager = JobManager(config)
    web_index = Path(__file__).resolve().parent.parent / "web" / "index.html"

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return web_index.read_text(encoding="utf-8")

    @app.post("/api/v1/jobs", response_model=JobStatusResponse)
    async def create_job(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> JobStatusResponse:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF upload is supported")

        original_filename = _safe_filename(file.filename)
        upload_dir = config.temp_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / f"{uuid.uuid4().hex}_{original_filename}"
        with upload_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        state = manager.create_job(upload_path=upload_path, input_filename=original_filename)
        background_tasks.add_task(_run_job, manager, config, state.job_id)
        return _build_status_response(manager.get(state.job_id))

    @app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
    def get_job(job_id: str) -> JobStatusResponse:
        try:
            state = manager.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        return _build_status_response(state)

    @app.get("/api/v1/jobs/{job_id}/download/{artifact}")
    def download_artifact(job_id: str, artifact: str):
        try:
            state = manager.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

        if artifact == "masked-pdf":
            if not state.masked_pdf_path or not state.masked_pdf_path.exists():
                raise HTTPException(status_code=404, detail="masked pdf not ready")
            return FileResponse(
                state.masked_pdf_path,
                filename=_download_filename(state.input_filename, ".masked.pdf"),
                media_type="application/pdf",
            )

        artifact_map = {
            "detections-csv": "detections_csv",
            "detections-jsonl": "detections_jsonl",
            "job-summary": "job_summary",
        }
        key = artifact_map.get(artifact)
        if key is None:
            raise HTTPException(status_code=404, detail="artifact not found")

        target = state.extra_files.get(key)
        if target is None or not target.exists():
            raise HTTPException(status_code=404, detail="artifact not ready")
        return FileResponse(target, filename=_download_filename(state.input_filename, _artifact_suffix(artifact)))

    return app


def _run_job(manager: JobManager, config: AppConfig, job_id: str) -> None:
    manager.mark_running(job_id)
    state = manager.get(job_id)
    try:
        pipeline = PIIMaskingPipeline(config=config)
        result = pipeline.run(state.upload_path)
        manager.mark_completed(
            job_id,
            result.output_dir,
            result.masked_pdf_path,
            page_successes=result.success_pages,
            page_failures=result.failed_pages,
        )
    except Exception as exc:  # pragma: no cover
        manager.mark_fail(job_id, str(exc))


def _build_status_response(state: JobState) -> JobStatusResponse:
    base = f"/api/v1/jobs/{state.job_id}/download"
    return JobStatusResponse(
        job_id=state.job_id,
        status=state.status,
        input_filename=state.input_filename,
        message=state.message,
        page_successes=state.page_successes,
        page_failures=state.page_failures,
        output_dir=str(state.output_dir) if state.output_dir else None,
        masked_pdf_url=f"{base}/masked-pdf" if state.masked_pdf_path else None,
        detections_csv_url=f"{base}/detections-csv" if state.extra_files.get("detections_csv") else None,
        detections_jsonl_url=f"{base}/detections-jsonl" if state.extra_files.get("detections_jsonl") else None,
        debug_dir_url=str(state.extra_files.get("debug_dir")) if state.extra_files.get("debug_dir") else None,
    )


def _safe_filename(value: str) -> str:
    normalized = value.replace("\\", "/").split("/")[-1].strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="invalid filename")
    return normalized


def _download_filename(input_filename: str, suffix: str) -> str:
    stem = Path(input_filename).stem or "document"
    return f"{stem}{suffix}"


def _artifact_suffix(artifact: str) -> str:
    suffixes = {
        "detections-csv": ".detections.csv",
        "detections-jsonl": ".detections.jsonl",
        "job-summary": ".job-summary.json",
    }
    return suffixes[artifact]
