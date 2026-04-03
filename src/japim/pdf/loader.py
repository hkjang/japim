from __future__ import annotations

from pathlib import Path

import fitz

from japim.common.models import PdfMetadata


class PDFLoader:
    def inspect(self, input_path: str | Path) -> PdfMetadata:
        path = Path(input_path)
        with fitz.open(path) as document:
            is_encrypted = bool(document.is_encrypted)
            if is_encrypted:
                raise ValueError(f"Encrypted PDF is not supported: {path}")

            return PdfMetadata(
                input_file=path,
                page_count=document.page_count,
                file_size=path.stat().st_size,
                is_encrypted=is_encrypted,
            )
