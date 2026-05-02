"""UI elements — badges, callout boxes, decorative lines, CTA buttons."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from hermesfy.composition.text_layer import FontPool


class Badge:
    """A floating badge with text (rectangular or circular)."""

    def __init__(
        self,
        text: str,
        style: str = "rectangular",  # "rectangular", "circular", "pill"
        bg_color: tuple[int, int, int, int] = (0, 255, 198, 255),
        text_color: tuple[int, int, int, int] = (10, 14, 20, 255),
        font_name: str = "inter",
        font_size: int = 14,
        position: str = "top-right",
        padding: int = 12,
        opacity: float = 1.0,
        border: bool = False,
        border_color: tuple[int, int, int, int] = (255, 255, 255, 128),
    ):
        self.text = text
        self.style = style
        self.bg_color = bg_color
        self.text_color = text_color
        self.font_name = font_name
        self.font_size = font_size
        self.position = position
        self.padding = padding
        self.opacity = opacity
        self.border = border
        self.border_color = border_color

    def render(self, canvas: Image.Image) -> Image.Image:
        font = FontPool.get(self.font_name, self.font_size)
        r, g, b, a = self.bg_color
        alpha = int(a * self.opacity)

        # Measure text
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = tmp.textbbox((0, 0), self.text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Badge dimensions
        bw = tw + self.padding * 2
        bh = th + self.padding * 2

        if self.style == "circular":
            side = max(bw, bh)
            bw = bh = side

        # Create badge
        badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(badge)

        if self.style == "pill":
            draw.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=bh // 2, fill=(r, g, b, alpha))
        elif self.style == "circular":
            draw.ellipse([(0, 0), (bw - 1, bh - 1)], fill=(r, g, b, alpha))
        else:
            draw.rectangle([(0, 0), (bw - 1, bh - 1)], fill=(r, g, b, alpha))

        if self.border:
            br, bg, bb, ba = self.border_color
            if self.style == "pill":
                draw.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=bh // 2, outline=(br, bg, bb, ba), width=2)
            elif self.style == "circular":
                draw.ellipse([(0, 0), (bw - 1, bh - 1)], outline=(br, bg, bb, ba), width=2)
            else:
                draw.rectangle([(0, 0), (bw - 1, bh - 1)], outline=(br, bg, bb, ba), width=2)

        # Text on badge
        tx = (bw - tw) // 2
        ty = (bh - th) // 2
        tr, tg, tb, ta = self.text_color
        draw.text((tx, ty), self.text, font=font, fill=(tr, tg, tb, int(ta * self.opacity)))

        # Position on canvas
        x, y = self._get_position(canvas.size, bw, bh)
        result = canvas.copy()
        result.paste(badge, (x, y), badge)
        return result

    def _get_position(self, canvas_size: tuple[int, int], bw: int, bh: int) -> tuple[int, int]:
        cw, ch = canvas_size
        m = int(cw * 0.04)
        positions = {
            "top-left": (m, m),
            "top-right": (cw - bw - m, m),
            "bottom-left": (m, ch - bh - m),
            "bottom-right": (cw - bw - m, ch - bh - m),
            "center": ((cw - bw) // 2, (ch - bh) // 2),
        }
        return positions.get(self.position, positions["top-right"])


class CalloutBox:
    """A callout box with title and description (like ASICS specs)."""

    def __init__(
        self,
        title: str,
        description: str = "",
        bg_color: tuple[int, int, int, int] = (255, 255, 255, 20),
        text_color: tuple[int, int, int, int] = (255, 255, 255, 255),
        title_font: str = "bebas",
        title_size: int = 24,
        desc_font: str = "inter",
        desc_size: int = 12,
        position: str = "bottom-left",
        padding: int = 16,
        width: int = 200,
        opacity: float = 0.9,
        border_color: tuple[int, int, int, int] = (255, 255, 255, 40),
    ):
        self.title = title
        self.description = description
        self.bg_color = bg_color
        self.text_color = text_color
        self.title_font = title_font
        self.title_size = title_size
        self.desc_font = desc_font
        self.desc_size = desc_size
        self.position = position
        self.padding = padding
        self.width = width
        self.opacity = opacity
        self.border_color = border_color

    def render(self, canvas: Image.Image) -> Image.Image:
        tf = FontPool.get(self.title_font, self.title_size)
        df = FontPool.get(self.desc_font, self.desc_size)
        r, g, b, a = self.bg_color
        alpha = int(a * self.opacity)

        # Measure
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        tb = tmp.textbbox((0, 0), self.title, font=tf)
        title_h = tb[3] - tb[1]

        desc_lines = []
        if self.description:
            words = self.description.split()
            line = ""
            for w in words:
                test = f"{line} {w}".strip()
                wb = tmp.textbbox((0, 0), test, font=df)
                if wb[2] - wb[0] <= self.width - self.padding * 2 or not line:
                    line = test
                else:
                    desc_lines.append(line)
                    line = w
            if line:
                desc_lines.append(line)

        desc_h = len(desc_lines) * int(self.desc_size * 1.4) if desc_lines else 0
        total_h = self.padding * 2 + title_h + (8 if desc_lines else 0) + desc_h

        # Create box
        box = Image.new("RGBA", (self.width, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(box)
        draw.rounded_rectangle(
            [(0, 0), (self.width - 1, total_h - 1)],
            radius=6, fill=(r, g, b, alpha)
        )
        # Border
        br, bg, bb, ba = self.border_color
        draw.rounded_rectangle(
            [(0, 0), (self.width - 1, total_h - 1)],
            radius=6, outline=(br, bg, bb, int(ba * self.opacity)), width=1
        )

        # Title
        tr, tg, tb_, ta = self.text_color
        draw.text((self.padding, self.padding), self.title, font=tf, fill=(tr, tg, tb_, int(ta * self.opacity)))

        # Description
        y = self.padding + title_h + 8
        for line in desc_lines:
            draw.text((self.padding, y), line, font=df, fill=(tr, tg, tb_, int(ta * 0.7 * self.opacity)))
            y += int(self.desc_size * 1.4)

        # Position
        x, y = self._get_position(canvas.size, self.width, total_h)
        result = canvas.copy()
        result.paste(box, (x, y), box)
        return result

    def _get_position(self, canvas_size, bw, bh):
        cw, ch = canvas_size
        m = int(cw * 0.04)
        positions = {
            "top-left": (m, m),
            "top-right": (cw - bw - m, m),
            "bottom-left": (m, ch - bh - m),
            "bottom-right": (cw - bw - m, ch - bh - m),
            "center": ((cw - bw) // 2, (ch - bh) // 2),
        }
        return positions.get(self.position, positions["bottom-left"])


class DecorativeLine:
    """A decorative horizontal or vertical line."""

    def __init__(
        self,
        color: tuple[int, int, int, int] = (255, 255, 255, 128),
        width: int = 2,
        length: int = 200,
        orientation: str = "horizontal",
        position: str = "center",
        opacity: float = 1.0,
    ):
        self.color = color
        self.width = width
        self.length = length
        self.orientation = orientation
        self.position = position
        self.opacity = opacity

    def render(self, canvas: Image.Image) -> Image.Image:
        r, g, b, a = self.color
        alpha = int(a * self.opacity)
        cw, ch = canvas.size
        m = int(cw * 0.04)

        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        if self.orientation == "horizontal":
            x = (cw - self.length) // 2
            y_positions = {
                "top": m, "center": ch // 2, "bottom": ch - m - self.width,
            }
            y = y_positions.get(self.position, ch // 2)
            draw.line([(x, y), (x + self.length, y)], fill=(r, g, b, alpha), width=self.width)
        else:
            y = (ch - self.length) // 2
            x_positions = {
                "left": m, "center": cw // 2, "right": cw - m - self.width,
            }
            x = x_positions.get(self.position, cw // 2)
            draw.line([(x, y), (x, y + self.length)], fill=(r, g, b, alpha), width=self.width)

        return Image.alpha_composite(canvas, layer)


class CTButton:
    """A call-to-action button."""

    def __init__(
        self,
        text: str,
        bg_color: tuple[int, int, int, int] = (0, 255, 198, 255),
        text_color: tuple[int, int, int, int] = (10, 14, 20, 255),
        font_name: str = "bebas",
        font_size: int = 20,
        position: str = "bottom-center",
        padding_x: int = 32,
        padding_y: int = 14,
        opacity: float = 1.0,
    ):
        self.text = text.upper()
        self.bg_color = bg_color
        self.text_color = text_color
        self.font_name = font_name
        self.font_size = font_size
        self.position = position
        self.padding_x = padding_x
        self.padding_y = padding_y
        self.opacity = opacity

    def render(self, canvas: Image.Image) -> Image.Image:
        font = FontPool.get(self.font_name, self.font_size)
        r, g, b, a = self.bg_color
        alpha = int(a * self.opacity)

        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = tmp.textbbox((0, 0), self.text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        bw = tw + self.padding_x * 2
        bh = th + self.padding_y * 2

        btn = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(btn)
        draw.rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=4, fill=(r, g, b, alpha))

        tr, tg, tb, ta = self.text_color
        draw.text(
            ((bw - tw) // 2, (bh - th) // 2),
            self.text, font=font,
            fill=(tr, tg, tb, int(ta * self.opacity))
        )

        cw, ch = canvas.size
        m = int(cw * 0.04)
        x = (cw - bw) // 2
        y_map = {
            "bottom-center": ch - bh - m,
            "center": (ch - bh) // 2,
            "top-center": m,
        }
        y = y_map.get(self.position, ch - bh - m)

        result = canvas.copy()
        result.paste(btn, (x, y), btn)
        return result
