"""Color grading — filters, toning, and style presets for consistent look."""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter


class ColorGrade:
    """Apply color grading to an image.

    Supports presets and manual adjustments.
    """

    @staticmethod
    def apply_preset(image: Image.Image, preset: str) -> Image.Image:
        """Apply a named color grading preset.

        Presets: 'warm', 'cool', 'cinematic', 'moody', 'editorial', 'vintage', 'high-contrast'
        """
        if preset == "warm":
            return ColorGrade._warm(image)
        elif preset == "cool":
            return ColorGrade._cool(image)
        elif preset == "cinematic":
            return ColorGrade._cinematic(image)
        elif preset == "moody":
            return ColorGrade._moody(image)
        elif preset == "editorial":
            return ColorGrade._editorial(image)
        elif preset == "vintage":
            return ColorGrade._vintage(image)
        elif preset == "high-contrast":
            return ColorGrade._high_contrast(image)
        return image

    @staticmethod
    def adjust(
        image: Image.Image,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: float = 1.0,
        warmth: float = 0.0,
    ) -> Image.Image:
        """Manual color adjustments."""
        img = image.copy()

        if brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(brightness)
        if contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)
        if saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(saturation)
        if sharpness != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(sharpness)
        if warmth != 0.0:
            img = ColorGrade._apply_warmth(img, warmth)

        return img

    @staticmethod
    def _warm(img: Image.Image) -> Image.Image:
        return ColorGrade.adjust(img, brightness=1.05, saturation=1.1, warmth=0.15)

    @staticmethod
    def _cool(img: Image.Image) -> Image.Image:
        return ColorGrade.adjust(img, brightness=1.02, saturation=0.9, warmth=-0.15)

    @staticmethod
    def _cinematic(img: Image.Image) -> Image.Image:
        img = ColorGrade.adjust(img, contrast=1.15, saturation=0.85, warmth=-0.05)
        # Teal shadows, orange highlights (simplified)
        return img

    @staticmethod
    def _moody(img: Image.Image) -> Image.Image:
        return ColorGrade.adjust(img, brightness=0.85, contrast=1.2, saturation=0.7, warmth=-0.1)

    @staticmethod
    def _editorial(img: Image.Image) -> Image.Image:
        return ColorGrade.adjust(img, contrast=1.1, saturation=0.95, sharpness=1.2)

    @staticmethod
    def _vintage(img: Image.Image) -> Image.Image:
        img = ColorGrade.adjust(img, brightness=1.05, contrast=0.9, saturation=0.75, warmth=0.2)
        return img

    @staticmethod
    def _high_contrast(img: Image.Image) -> Image.Image:
        return ColorGrade.adjust(img, contrast=1.35, saturation=1.1, sharpness=1.1)

    @staticmethod
    def _apply_warmth(image: Image.Image, warmth: float) -> Image.Image:
        """Shift color temperature. Positive = warmer, negative = cooler."""
        if warmth == 0:
            return image
        img = image.copy().convert("RGB")
        r, g, b = img.split()
        shift = int(warmth * 30)
        r = r.point(lambda x: min(255, max(0, x + shift)))
        b = b.point(lambda x: min(255, max(0, x - shift)))
        return Image.merge("RGB", (r, g, b)).convert("RGBA")
