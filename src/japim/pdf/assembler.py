from __future__ import annotations

from pathlib import Path

from PIL import Image


class PDFAssembler:
    def assemble(self, image_paths: list[Path], output_pdf_path: Path) -> Path:
        if not image_paths:
            raise ValueError("No images supplied for PDF assembly")

        images = [Image.open(path).convert("RGB") for path in image_paths]
        first, rest = images[0], images[1:]
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        first.save(output_pdf_path, save_all=True, append_images=rest, resolution=300.0)

        for image in images:
            image.close()

        return output_pdf_path
