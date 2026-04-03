# Architecture

## Flow

1. REST API receives an uploaded PDF.
2. File is saved into the temporary upload area.
3. `PIIMaskingPipeline` renders the PDF to per-page PNG.
4. Image preprocessing improves OCR readiness.
5. PaddleOCR extracts text and polygons.
6. Line reconstruction merges OCR tokens for rule matching.
7. Rules detect PII spans and derive partial-mask character ranges.
8. Character ranges are mapped back to image rectangles.
9. Masker applies box, blur, or pixelate masking to the rendered page.
10. Masked PNG pages are reassembled into a PDF.
11. Audit logs are written as JSONL, CSV, and summary JSON.
12. API exposes job status and file download endpoints.

## Main modules

- `japim.api`: upload/download REST API and browser test page
- `japim.pipeline`: orchestration layer
- `japim.pdf`: PDF validation, rendering, and assembly
- `japim.preprocess`: OCR-focused preprocessing
- `japim.ocr`: PaddleOCR adapter
- `japim.postprocess`: line reconstruction
- `japim.rules`: rule-based PII detection
- `japim.masking`: bbox mapping and image masking
- `japim.audit`: audit artifact generation
