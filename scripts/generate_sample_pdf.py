from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "samples" / "generated"
MOCK_DIR = ROOT / "samples" / "mock_ocr"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an OCR-friendly sample PDF and matching mock OCR fixture")
    parser.add_argument("--korean", action="store_true", help="Render a Korean sample when a Korean-capable TTF is available")
    parser.add_argument("--font-path", type=Path, help="Explicit path to a TTF font file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MOCK_DIR.mkdir(parents=True, exist_ok=True)

    lines = build_lines(args.korean)
    font_path = resolve_font_path(args.font_path, prefer_korean=args.korean)

    page_image = render_sample_image(lines, font_path)
    image_path = OUTPUT_DIR / "sample-e2e.png"
    page_image.save(image_path)

    pdf_path = OUTPUT_DIR / "sample-e2e.pdf"
    save_image_as_pdf(page_image, pdf_path)

    payload = build_mock_payload(lines)
    (MOCK_DIR / "page_0001.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(f"sample_pdf={pdf_path}")
    print(f"sample_png={image_path}")
    print(f"mock_ocr={MOCK_DIR / 'page_0001.json'}")
    print(f"font_path={font_path if font_path else 'PillowDefault'}")


def build_lines(korean: bool) -> list[str]:
    if korean:
        return [
            "휴대폰 010-1234-5678",
            "이메일 abcdef@example.com",
        ]
    return [
        "MOBILE 010-1234-5678",
        "EMAIL abcdef@example.com",
    ]


def resolve_font_path(explicit: Path | None, prefer_korean: bool) -> Path | None:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)

    if prefer_korean:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/malgun.ttf"),
                Path("C:/Windows/Fonts/NanumGothic.ttf"),
                Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/arial.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def render_sample_image(lines: list[str], font_path: Path | None) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = load_font(font_path)

    positions = [(72, 120), (72, 240)]
    for text, (x, y) in zip(lines, positions, strict=False):
        draw.text((x, y), text, fill="black", font=font)
    return image


def load_font(font_path: Path | None) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    if font_path is not None:
        return ImageFont.truetype(str(font_path), size=48)
    return ImageFont.load_default()


def save_image_as_pdf(image: Image.Image, target_path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    image_bytes = image_to_png_bytes(image)
    rect = fitz.Rect(0, 0, 595, 842)
    page.insert_image(rect, stream=image_bytes)
    document.save(target_path)
    document.close()


def image_to_png_bytes(image: Image.Image) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_mock_payload(lines: list[str]) -> list[dict[str, object]]:
    return [
        {
            "text": lines[0],
            "confidence": 0.99,
            "polygon": [[72, 120], [620, 120], [620, 172], [72, 172]],
        },
        {
            "text": lines[1],
            "confidence": 0.99,
            "polygon": [[72, 240], [760, 240], [760, 292], [72, 292]],
        },
    ]


if __name__ == "__main__":
    main()
