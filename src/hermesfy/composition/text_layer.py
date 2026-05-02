"""Typography engine — professional text rendering with font management."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

_FONTS_DIR = Path(__file__).parent / "fonts"

# Font registry: name → file
_FONT_MAP = {
    "inter": "Inter.ttf",
    "playfair": "PlayfairDisplay.ttf",
    "bebas": "BebasNeue.ttf",
    "jetbrains": "JetBrainsMono.ttf",
    "roboto": "Roboto.ttf",
}


class FontPool:
    """Lazy-loading font cache."""

    _cache: dict[str, ImageFont.FreeTypeFont] = {}

    @classmethod
    def get(cls, name: str, size: int) -> ImageFont.FreeTypeFont:
        """Get a font by name and size. Caches for reuse."""
        key = f"{name}:{size}"
        if key not in cls._cache:
            filename = _FONT_MAP.get(name.lower(), name)
            font_path = _FONTS_DIR / filename
            if not font_path.exists():
                # Fallback to default
                cls._cache[key] = ImageFont.load_default()
            else:
                cls._cache[key] = ImageFont.truetype(str(font_path), size)
        return cls._cache[key]

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()


class TextLayer:
    """A composable text layer for the multi-layer composition engine.

    Supports: title, subtitle, body text, accent text, watermark.
    Handles: text wrapping, alignment, shadow, opacity, positioning.
    """

    def __init__(
        self,
        text: str,
        font_name: str = "inter",
        font_size: int = 48,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        position: str = "center",  # "center", "left", "right", "top-left", etc.
        max_width: int = 0,  # 0 = no wrapping
        line_spacing: float = 1.2,
        shadow: bool = False,
        shadow_color: tuple[int, int, int, int] = (0, 0, 0, 128),
        shadow_offset: tuple[int, int] = (2, 2),
        opacity: float = 1.0,
        uppercase: bool = False,
        letter_spacing: int = 0,
        anchor: str = "lt",  # Pillow text anchor
    ):
        self.text = text.upper() if uppercase else text
        self.font_name = font_name
        self.font_size = font_size
        self.color = color
        self.position = position
        self.max_width = max_width
        self.line_spacing = line_spacing
        self.shadow = shadow
        self.shadow_color = shadow_color
        self.shadow_offset = shadow_offset
        self.opacity = opacity
        self.letter_spacing = letter_spacing
        self.anchor = anchor

    def render(self, canvas: Image.Image) -> Image.Image:
        """Render this text layer onto the canvas.

        Args:
            canvas: Base image to render on (RGBA).

        Returns:
            New image with text composited.
        """
        font = FontPool.get(self.font_name, self.font_size)

        # Apply opacity to color
        r, g, b, a = self.color
        alpha = int(a * self.opacity)
        color = (r, g, b, alpha)

        # Create text layer
        txt_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        # Wrap text if max_width set
        lines = self._wrap_text(draw, font) if self.max_width > 0 else [self.text]

        # Calculate total text height
        line_height = int(self.font_size * self.line_spacing)
        total_height = line_height * len(lines)

        # Calculate position
        x, y = self._get_position(canvas.size, total_height)

        # Draw each line
        for i, line in enumerate(lines):
            ly = y + i * line_height

            # Shadow
            if self.shadow:
                sr, sg, sb, sa = self.shadow_color
                shadow_alpha = int(sa * self.opacity)
                draw.text(
                    (x + self.shadow_offset[0], ly + self.shadow_offset[1]),
                    line,
                    font=font,
                    fill=(sr, sg, sb, shadow_alpha),
                    anchor=self.anchor,
                )

            # Main text
            draw.text((x, ly), line, font=font, fill=color, anchor=self.anchor)

        # Composite onto canvas
        return Image.alpha_composite(canvas, txt_layer)

    def _wrap_text(self, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> list[str]:
        """Word-wrap text to fit within max_width."""
        words = self.text.split()
        lines = []
        current = ""

        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
            if w <= self.max_width or not current:
                current = test
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)
        return lines or [self.text]

    def _get_position(self, canvas_size: tuple[int, int], text_height: int) -> tuple[int, int]:
        """Calculate x, y from position string."""
        cw, ch = canvas_size
        margin = int(cw * 0.04)

        positions = {
            "center": (cw // 2, (ch - text_height) // 2),
            "top": (cw // 2, margin),
            "bottom": (cw // 2, ch - text_height - margin),
            "left": (margin, ch // 2),
            "right": (cw - margin, ch // 2),
            "top-left": (margin, margin),
            "top-right": (cw - margin, margin),
            "bottom-left": (margin, ch - text_height - margin),
            "bottom-right": (cw - margin, ch - text_height - margin),
        }
        return positions.get(self.position, positions["center"])


def text_title(text: str, **kwargs) -> TextLayer:
    """Create a title text layer (large, bold)."""
    defaults = {"font_name": "bebas", "font_size": 72, "uppercase": True}
    defaults.update(kwargs)
    return TextLayer(text, **defaults)


def text_subtitle(text: str, **kwargs) -> TextLayer:
    """Create a subtitle text layer (medium, elegant)."""
    defaults = {"font_name": "playfair", "font_size": 36}
    defaults.update(kwargs)
    return TextLayer(text, **defaults)


def text_body(text: str, **kwargs) -> TextLayer:
    """Create a body text layer (small, readable)."""
    defaults = {"font_name": "inter", "font_size": 18}
    defaults.update(kwargs)
    return TextLayer(text, **defaults)


def text_accent(text: str, **kwargs) -> TextLayer:
    """Create an accent text layer (mono, technical)."""
    defaults = {"font_name": "jetbrains", "font_size": 14, "uppercase": True}
    defaults.update(kwargs)
    return TextLayer(text, **defaults)


def text_watermark(text: str, canvas_width: int = 1024, **kwargs) -> TextLayer:
    """Create a giant watermark text layer (behind product)."""
    font_size = int(canvas_width * 0.15)
    defaults = {
        "font_name": "bebas",
        "font_size": font_size,
        "opacity": 0.15,
        "position": "center",
        "color": (255, 255, 255, 255),
    }
    defaults.update(kwargs)
    return TextLayer(text, **defaults)
