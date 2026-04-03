from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


class ImagePreprocessor:
    def __init__(
        self,
        enable_grayscale: bool,
        enable_binarize: bool,
        enable_denoise: bool,
        enable_deskew: bool,
        min_short_edge: int,
    ) -> None:
        self.enable_grayscale = enable_grayscale
        self.enable_binarize = enable_binarize
        self.enable_denoise = enable_denoise
        self.enable_deskew = enable_deskew
        self.min_short_edge = min_short_edge

    def process(self, image_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if cv2 is None:  # pragma: no cover
            shutil.copy2(image_path, output_path)
            return output_path

        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        image = self._upscale_if_needed(image)
        if self.enable_deskew:
            image = self._deskew(image)

        if self.enable_grayscale:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self.enable_denoise:
            image = cv2.medianBlur(image, 3)

        if self.enable_binarize:
            image = cv2.adaptiveThreshold(
                image,
                maxValue=255,
                adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                thresholdType=cv2.THRESH_BINARY,
                blockSize=25,
                C=15,
            )

        cv2.imwrite(str(output_path), image)
        return output_path

    def _upscale_if_needed(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        short_edge = min(height, width)
        if short_edge >= self.min_short_edge:
            return image

        scale = self.min_short_edge / short_edge
        return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, threshold = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coordinates = np.column_stack(np.where(threshold > 0))
        if len(coordinates) < 20:
            return image

        angle = cv2.minAreaRect(coordinates)[-1]
        if angle < -45:
            angle = 90 + angle
        angle = -angle
        if math.isclose(angle, 0.0, abs_tol=0.3):
            return image

        height, width = image.shape[:2]
        center = (width / 2, height / 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
