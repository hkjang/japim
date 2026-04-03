from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class PaddleConfig(BaseModel):
    use_gpu: bool = False
    device: str = "cpu"
    det_model_dir: Path | None = None
    rec_model_dir: Path | None = None
    cls_model_dir: Path | None = None
    show_log: bool = False


class AuditConfig(BaseModel):
    write_csv: bool = True
    write_jsonl: bool = True
    write_summary: bool = True


class AppConfig(BaseModel):
    job_name_prefix: str = "japim"
    input_dir: Path = Path("input")
    output_dir: Path = Path("output")
    temp_dir: Path = Path("temp")

    dpi: int = 300
    ocr_backend: Literal["paddle", "mock"] = "paddle"
    ocr_lang: str = "korean"
    use_angle_cls: bool = True
    confidence_threshold: float = 0.45
    auxiliary_confidence_threshold: float = 0.25
    mock_ocr_dir: Path | None = None

    enable_grayscale: bool = True
    enable_binarize: bool = False
    enable_denoise: bool = True
    enable_deskew: bool = True
    min_short_edge: int = 1800
    line_merge_tolerance_px: float = 24.0
    token_gap_multiplier: float = 0.65

    mask_padding: int = 6
    mask_style: Literal["box", "blur", "pixelate"] = "box"
    mask_color: tuple[int, int, int] = (0, 0, 0)
    blur_radius: int = 10
    pixelate_block_size: int = 12

    stop_on_error: bool = False
    save_debug_image: bool = True
    save_ocr_json: bool = True
    save_preprocessed_image: bool = False

    enabled_rules: list[str] = Field(default_factory=list)
    paddle: PaddleConfig = Field(default_factory=PaddleConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)

    def ensure_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)
