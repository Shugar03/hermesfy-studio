"""Multi-layer composition engine — stack layers into a final ad image."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance


@dataclass
class Layer:
    """A single layer in the composition."""
    type: str  # "image", "gradient", "solid", "blur"
    data: Any = None
    opacity: float = 1.0
    position: tuple[int, int] = (0, 0)
    size: tuple[int, int] = (0, 0)  # 0,0 = no resize
    blend: str = "normal"  # "normal", "multiply", "screen", "overlay"


class Composer:
    """Build and render multi-layer ad compositions.

    Usage:
        c = Composer(width=1080, height=1080)
        c.add_solid_bg((10, 14, 20))
        c.add_image(product_img, position="center")
        c.add_text("TITLE", font="bebas", size=72, position="top")
        c.add_badge("$29.99", position="bottom-right")
        result = c.render()
    """

    def __init__(self, width: int = 1080, height: int = 1080):
        self.width = width
        self.height = height
        self.canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        self.layers: list[Layer] = []

    def add_solid_bg(
        self,
        color: tuple[int, int, int] | tuple[int, int, int, int],
    ) -> Composer:
        """Set a solid background color."""
        if len(color) == 3:
            color = (*color, 255)
        self.canvas = Image.new("RGBA", (self.width, self.height), color)
        return self

    def add_gradient_bg(
        self,
        top_color: tuple[int, int, int],
        bottom_color: tuple[int, int, int],
        direction: str = "vertical",
    ) -> Composer:
        """Add a gradient background."""
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        steps = self.height if direction == "vertical" else self.width
        for i in range(steps):
            ratio = i / max(steps - 1, 1)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
            if direction == "vertical":
                draw.line([(0, i), (self.width, i)], fill=(r, g, b, 255))
            else:
                draw.line([(i, 0), (i, self.height)], fill=(r, g, b, 255))

        self.canvas = layer
        return self

    def add_split_bg(
        self,
        left_color: tuple[int, int, int],
        right_color: tuple[int, int, int],
        split_ratio: float = 0.5,
    ) -> Composer:
        """Add a split background (left/right)."""
        self.canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(self.canvas)
        split_x = int(self.width * split_ratio)
        draw.rectangle([(0, 0), (split_x, self.height)], fill=(*left_color, 255))
        draw.rectangle([(split_x, 0), (self.width, self.height)], fill=(*right_color, 255))
        return self

    def add_image_layer(
        self,
        img: Image.Image,
        position: str = "center",
        scale: float = 1.0,
        opacity: float = 1.0,
    ) -> Composer:
        """Add an image layer (e.g., product photo)."""
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if scale != 1.0:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        if opacity < 1.0:
            r, g, b, a = img.split()
            a = a.point(lambda x: int(x * opacity))
            img = Image.merge("RGBA", (r, g, b, a))

        x, y = self._calc_position(position, img.width, img.height)
        self.canvas.paste(img, (x, y), img)
        return self

    def add_text_layer(self, text_layer) -> Composer:
        """Add a TextLayer object."""
        self.canvas = text_layer.render(self.canvas)
        return self

    def add_ui_element(self, element) -> Composer:
        """Add a UI element (Badge, CalloutBox, etc.)."""
        self.canvas = element.render(self.canvas)
        return self

    def add_blur_overlay(self, intensity: int = 20) -> Composer:
        """Apply blur to the current canvas (for background effects)."""
        self.canvas = self.canvas.filter(ImageFilter.GaussianBlur(radius=intensity))
        return self

    def add_vignette(self, intensity: float = 0.3) -> Composer:
        """Add a subtle vignette overlay."""
        vignette = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)

        cx, cy = self.width // 2, self.height // 2
        max_r = int((cx**2 + cy**2) ** 0.5)

        for r in range(max_r, 0, -2):
            alpha = int(255 * intensity * (r / max_r) ** 2)
            alpha = min(alpha, 255)
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                fill=(0, 0, 0, alpha),
            )

        self.canvas = Image.alpha_composite(self.canvas, vignette)
        return self

    def add_noise_texture(self, opacity: float = 0.03) -> Composer:
        """Add subtle noise texture for depth."""
        import random
        noise = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(noise)
        for _ in range(int(self.width * self.height * opacity)):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            v = random.randint(0, 255)
            draw.point((x, y), fill=(v, v, v, 20))
        self.canvas = Image.alpha_composite(self.canvas, noise)
        return self

    def render(self) -> Image.Image:
        """Return the final composited image."""
        return self.canvas.copy()

    def render_rgb(self) -> Image.Image:
        """Return as RGB (for JPEG/saving)."""
        return self.canvas.convert("RGB")

    def save(self, path: str | Path, quality: int = 95) -> Path:
        """Render and save to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.render_rgb().save(str(path), quality=quality)
        return path

    def _calc_position(self, position: str, elem_w: int, elem_h: int) -> tuple[int, int]:
        """Calculate position for an element on the canvas."""
        cw, ch = self.width, self.height
        m = int(cw * 0.04)
        positions = {
            "center": ((cw - elem_w) // 2, (ch - elem_h) // 2),
            "top": ((cw - elem_w) // 2, m),
            "bottom": ((cw - elem_w) // 2, ch - elem_h - m),
            "left": (m, (ch - elem_h) // 2),
            "right": (cw - elem_w - m, (ch - elem_h) // 2),
            "top-left": (m, m),
            "top-right": (cw - elem_w - m, m),
            "bottom-left": (m, ch - elem_h - m),
            "bottom-right": (cw - elem_w - m, ch - elem_h - m),
        }
        return positions.get(position, positions["center"])
