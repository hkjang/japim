from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download PaddleOCR 3.x model files into a deterministic directory")
    parser.add_argument("--output-dir", default="models/paddleocr", help="Target directory for det/rec/cls model folders")
    parser.add_argument("--lang", default="korean", help="PaddleOCR language code")
    parser.add_argument("--use-angle-cls", action="store_true", default=True, help="Download the text line orientation model too")
    parser.add_argument("--cache-dir", default="var/paddle-cache", help="Base directory used for PaddleOCR model downloads")
    parser.add_argument("--text-detection-model-name", default="PP-OCRv5_mobile_det", help="Official PaddleOCR detection model name")
    parser.add_argument("--text-recognition-model-name", default=None, help="Official PaddleOCR recognition model name")
    parser.add_argument("--textline-orientation-model-name", default="PP-LCNet_x0_25_textline_ori", help="Official PaddleOCR text line orientation model name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    cache_dir = Path(args.cache_dir).resolve()

    if output_dir.exists():
        shutil.rmtree(output_dir)

    os.environ.setdefault("PADDLE_OCR_BASE_DIR", str(cache_dir))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    from paddleocr import PaddleOCR

    recognition_model_name = args.text_recognition_model_name or default_recognition_model_name(args.lang)
    ocr = PaddleOCR(
        lang=args.lang,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=args.use_angle_cls,
        text_detection_model_name=args.text_detection_model_name,
        text_recognition_model_name=recognition_model_name,
        textline_orientation_model_name=args.textline_orientation_model_name if args.use_angle_cls else None,
    )

    model_dirs = discover_model_dirs(
        ocr,
        cache_dir=cache_dir,
        include_textline=args.use_angle_cls,
        model_names={
            "det": args.text_detection_model_name,
            "rec": recognition_model_name,
            "cls": args.textline_orientation_model_name,
        },
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    for key, source_dir in model_dirs.items():
        target_dir = output_dir / key
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        print(f"{key}={target_dir}")


def discover_model_dirs(ocr, cache_dir: Path, include_textline: bool, model_names: dict[str, str]) -> dict[str, Path]:
    exported = export_model_dirs(ocr)
    search_roots = build_search_roots(cache_dir)

    hints = {
        "det": (model_names["det"].lower(), "_det"),
        "rec": (model_names["rec"].lower(), "_rec"),
        "cls": (model_names["cls"].lower(), "_ori"),
    }

    resolved: dict[str, Path] = {}
    for component in ("det", "rec"):
        path = match_exported_dir(exported, hints[component])
        if path is None:
            path = search_model_dir(search_roots, hints[component])
        if path is None:
            raise RuntimeError(f"Unable to locate downloaded {component} model directory")
        resolved[component] = path

    if include_textline:
        path = match_exported_dir(exported, hints["cls"])
        if path is None:
            path = search_model_dir(search_roots, hints["cls"])
        if path is None:
            raise RuntimeError("Unable to locate downloaded cls model directory")
        resolved["cls"] = path

    return resolved


def export_model_dirs(ocr) -> list[Path]:
    export_method = getattr(ocr, "export_paddlex_config_to_yaml", None)
    if export_method is None:
        return []

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as handle:
        export_path = Path(handle.name)

    try:
        export_method(str(export_path))
        data = yaml.safe_load(export_path.read_text(encoding="utf-8")) or {}
    finally:
        export_path.unlink(missing_ok=True)

    raw_paths: list[str] = []
    collect_model_dir_values(data, raw_paths)
    return [Path(value) for value in raw_paths if value]


def collect_model_dir_values(node, values: list[str]) -> None:
    if isinstance(node, dict):
        model_dir = node.get("model_dir")
        if isinstance(model_dir, str):
            values.append(model_dir)
        for value in node.values():
            collect_model_dir_values(value, values)
        return

    if isinstance(node, list):
        for value in node:
            collect_model_dir_values(value, values)


def build_search_roots(cache_dir: Path) -> list[Path]:
    home = Path.home()
    roots = [
        home / ".paddlex" / "official_models",
        home / ".paddlex",
        cache_dir / "official_models",
        cache_dir / ".paddlex" / "official_models",
        cache_dir / ".paddlex",
        cache_dir,
    ]
    return [root for root in roots if root.exists()]


def match_exported_dir(paths: list[Path], hints: tuple[str, ...]) -> Path | None:
    lowered_hints = tuple(hint.lower() for hint in hints)
    for path in paths:
        haystack = path.as_posix().lower()
        if path.exists() and has_model_files(path) and any(hint in haystack for hint in lowered_hints):
            return path
    return None


def search_model_dir(search_roots: list[Path], hints: tuple[str, ...]) -> Path | None:
    lowered_hints = tuple(hint.lower() for hint in hints)
    for root in search_roots:
        for candidate in root.rglob("*"):
            if not candidate.is_dir():
                continue
            haystack = candidate.as_posix().lower()
            if not any(hint in haystack for hint in lowered_hints):
                continue
            if has_model_files(candidate):
                return candidate
    return None


def has_model_files(path: Path) -> bool:
    return (path / "inference.pdiparams").exists() and (path / "inference.yml").exists()


def default_recognition_model_name(lang: str) -> str:
    return f"{lang.lower()}_PP-OCRv5_mobile_rec"


if __name__ == "__main__":
    main()
