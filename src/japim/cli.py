from __future__ import annotations

import argparse

import uvicorn

from japim.api.app import create_app
from japim.common.config import load_config
from japim.pipeline import PIIMaskingPipeline


def parse_pages(value: str | None) -> set[int] | None:
    if not value:
        return None

    pages: set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", maxsplit=1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(chunk))
    return pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="japim", description="PaddleOCR based PDF PII masking tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run masking pipeline for a PDF")
    run_parser.add_argument("--input", required=True, help="Input PDF path")
    run_parser.add_argument("--config", required=True, help="YAML configuration path")
    run_parser.add_argument("--pages", help="Optional page range like 1,3-5")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    serve_parser = subparsers.add_parser("serve", help="Run REST API server")
    serve_parser.add_argument("--config", default="configs/default.yaml", help="YAML configuration path")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)
        pipeline = PIIMaskingPipeline(config=config, verbose=args.verbose)
        result = pipeline.run(args.input, selected_pages=parse_pages(args.pages))
        print(f"job_id={result.job_id}")
        print(f"masked_pdf={result.masked_pdf_path}")
        print(f"output_dir={result.output_dir}")
        return

    if args.command == "serve":
        app = create_app(args.config)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
