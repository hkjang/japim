from __future__ import annotations

from pathlib import Path

import fitz

from japim.common.models import RenderedPage


class PDFRenderer:
    def __init__(self, dpi: int) -> None:
        self.dpi = dpi

    def render(self, input_path: str | Path, output_dir: Path, selected_pages: set[int] | None = None) -> list[RenderedPage]:
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered_pages: list[RenderedPage] = []

        with fitz.open(input_path) as document:
            for index, page in enumerate(document, start=1):
                if selected_pages and index not in selected_pages:
                    continue

                pixmap = page.get_pixmap(dpi=self.dpi, alpha=False)
                image_path = output_dir / f"page_{index:04d}.png"
                pixmap.save(image_path)
                rendered_pages.append(
                    RenderedPage(
                        page_no=index,
                        image_path=image_path,
                        width=pixmap.width,
                        height=pixmap.height,
                    )
                )

        return rendered_pages
