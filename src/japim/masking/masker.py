from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from japim.common.models import Rect, RuleMatch


class ImageMasker:
    def __init__(self, style: str, color: tuple[int, int, int], blur_radius: int, pixelate_block_size: int) -> None:
        self.style = style
        self.color = color
        self.blur_radius = blur_radius
        self.pixelate_block_size = pixelate_block_size

    def apply(self, image_path: Path, output_path: Path, matches: list[RuleMatch]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.open(image_path).convert("RGB")

        if self.style == "box":
            image = self._apply_box(image, matches)
        elif self.style == "blur":
            image = self._apply_blur(image, matches)
        elif self.style == "pixelate":
            image = self._apply_pixelate(image, matches)
        else:
            raise ValueError(f"Unsupported mask style: {self.style}")

        image.save(output_path)
        image.close()
        return output_path

    def create_debug_overlay(self, image_path: Path, output_path: Path, matches: list[RuleMatch]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        for match in matches:
            for bbox in match.bboxes:
                draw.rectangle(bbox, outline=(255, 0, 0), width=3)
        image.save(output_path)
        image.close()
        return output_path

    def _apply_box(self, image: Image.Image, matches: list[RuleMatch]) -> Image.Image:
        draw = ImageDraw.Draw(image)
        for match in matches:
            for bbox in match.bboxes:
                draw.rectangle(bbox, fill=self.color)
        return image

    def _apply_blur(self, image: Image.Image, matches: list[RuleMatch]) -> Image.Image:
        for match in matches:
            for bbox in match.bboxes:
                image = self._process_crop(image, bbox, "blur")
        return image

    def _apply_pixelate(self, image: Image.Image, matches: list[RuleMatch]) -> Image.Image:
        for match in matches:
            for bbox in match.bboxes:
                image = self._process_crop(image, bbox, "pixelate")
        return image

    def _process_crop(self, image: Image.Image, bbox: Rect, mode: str) -> Image.Image:
        left, top, right, bottom = [int(value) for value in bbox]
        crop = image.crop((left, top, right, bottom))
        if mode == "blur":
            crop = crop.filter(ImageFilter.GaussianBlur(radius=self.blur_radius))
        else:
            reduced = crop.resize(
                (
                    max(1, crop.width // self.pixelate_block_size),
                    max(1, crop.height // self.pixelate_block_size),
                ),
                Image.Resampling.BILINEAR,
            )
            crop = reduced.resize(crop.size, Image.Resampling.NEAREST)
        image.paste(crop, (left, top, right, bottom))
        return image
