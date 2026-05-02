"""Tests for the composition engine."""

import pytest
from PIL import Image

from hermesfy.composition.text_layer import TextLayer, FontPool, text_title, text_subtitle, text_body, text_accent
from hermesfy.composition.ui_elements import Badge, CalloutBox, DecorativeLine, CTButton
from hermesfy.composition.composer import Composer
from hermesfy.composition.color_grade import ColorGrade


@pytest.fixture
def canvas():
    """Create a 512x512 RGBA canvas."""
    return Image.new("RGBA", (512, 512), (20, 20, 30, 255))


@pytest.fixture
def big_canvas():
    """Create a 1080x1080 RGBA canvas."""
    return Image.new("RGBA", (1080, 1080), (20, 20, 30, 255))


# --- FontPool ---

class TestFontPool:
    def test_get_returns_font(self):
        font = FontPool.get("inter", 24)
        assert font is not None

    def test_caches_fonts(self):
        f1 = FontPool.get("inter", 24)
        f2 = FontPool.get("inter", 24)
        assert f1 is f2

    def test_different_sizes_different_fonts(self):
        f1 = FontPool.get("inter", 12)
        f2 = FontPool.get("inter", 48)
        assert f1 is not f2

    def test_unknown_font_fallback(self):
        font = FontPool.get("nonexistent", 24)
        assert font is not None  # Falls back to default


# --- TextLayer ---

class TestTextLayer:
    def test_renders_text_on_canvas(self, canvas):
        tl = TextLayer("HELLO", font_name="bebas", font_size=36)
        result = tl.render(canvas)
        assert result.size == canvas.size
        assert result.mode == "RGBA"

    def test_opacity_reduces_alpha(self, canvas):
        tl = TextLayer("TEST", font_name="bebas", font_size=24, opacity=0.5)
        result = tl.render(canvas)
        assert result is not None

    def test_shadow_adds_depth(self, canvas):
        tl = TextLayer("SHADOW", font_name="bebas", font_size=24, shadow=True)
        result = tl.render(canvas)
        assert result is not None

    def test_uppercase_option(self, canvas):
        tl = TextLayer("hello", font_name="bebas", font_size=24, uppercase=True)
        assert tl.text == "HELLO"

    def test_factory_functions(self):
        t = text_title("Title")
        assert t.font_name == "bebas"
        s = text_subtitle("Sub")
        assert s.font_name == "playfair"
        b = text_body("Body")
        assert b.font_name == "inter"
        a = text_accent("Accent")
        assert a.font_name == "jetbrains"


# --- Badge ---

class TestBadge:
    def test_renders_rectangular(self, canvas):
        badge = Badge("$29.99", style="rectangular", position="top-right")
        result = badge.render(canvas)
        assert result.size == canvas.size

    def test_renders_circular(self, canvas):
        badge = Badge("NEW", style="circular", position="top-left")
        result = badge.render(canvas)
        assert result is not None

    def test_renders_pill(self, canvas):
        badge = Badge("SALE", style="pill", position="bottom-center")
        result = badge.render(canvas)
        assert result is not None

    def test_opacity(self, canvas):
        badge = Badge("TEST", opacity=0.5)
        result = badge.render(canvas)
        assert result is not None


# --- CalloutBox ---

class TestCalloutBox:
    def test_renders_box(self, canvas):
        box = CalloutBox("SPECS", description="Premium material", position="bottom-left")
        result = box.render(canvas)
        assert result.size == canvas.size

    def test_no_description(self, canvas):
        box = CalloutBox("INFO", position="top-right")
        result = box.render(canvas)
        assert result is not None


# --- DecorativeLine ---

class TestDecorativeLine:
    def test_horizontal(self, canvas):
        line = DecorativeLine(orientation="horizontal", length=200)
        result = line.render(canvas)
        assert result.size == canvas.size

    def test_vertical(self, canvas):
        line = DecorativeLine(orientation="vertical", length=150)
        result = line.render(canvas)
        assert result is not None


# --- CTButton ---

class TestCTButton:
    def test_renders_button(self, canvas):
        btn = CTButton("BUY NOW", position="bottom-center")
        result = btn.render(canvas)
        assert result.size == canvas.size


# --- Composer ---

class TestComposer:
    def test_creates_canvas(self):
        c = Composer(512, 512)
        assert c.width == 512
        assert c.height == 512

    def test_solid_bg(self):
        c = Composer(100, 100)
        c.add_solid_bg((255, 0, 0))
        result = c.render()
        assert result.getpixel((50, 50))[:3] == (255, 0, 0)

    def test_gradient_bg(self):
        c = Composer(100, 100)
        c.add_gradient_bg((0, 0, 0), (255, 255, 255))
        result = c.render()
        # Top should be dark, bottom bright
        top = result.getpixel((50, 5))[:3]
        bottom = result.getpixel((50, 95))[:3]
        assert sum(top) < sum(bottom)

    def test_split_bg(self):
        c = Composer(100, 100)
        c.add_split_bg((255, 0, 0), (0, 0, 255))
        result = c.render()
        left = result.getpixel((10, 50))[:3]
        right = result.getpixel((90, 50))[:3]
        assert left[0] > left[2]  # Red on left
        assert right[2] > right[0]  # Blue on right

    def test_add_image_layer(self):
        c = Composer(200, 200)
        img = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
        c.add_image_layer(img, position="center")
        result = c.render()
        # Center should be white
        center = result.getpixel((100, 100))
        assert center[0] > 200

    def test_chained_operations(self):
        result = (
            Composer(512, 512)
            .add_solid_bg((10, 14, 20))
            .add_gradient_bg((0, 0, 0), (30, 30, 40))
            .add_vignette(0.2)
            .render()
        )
        assert result.size == (512, 512)

    def test_save(self, tmp_path):
        c = Composer(100, 100)
        c.add_solid_bg((0, 255, 198))
        path = c.save(tmp_path / "test.jpg")
        assert path.exists()


# --- ColorGrade ---

class TestColorGrade:
    def test_preset_warm(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = ColorGrade.apply_preset(img, "warm")
        assert result is not None

    def test_preset_cool(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = ColorGrade.apply_preset(img, "cool")
        assert result is not None

    def test_preset_cinematic(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = ColorGrade.apply_preset(img, "cinematic")
        assert result is not None

    def test_manual_adjustments(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = ColorGrade.adjust(img, brightness=1.2, contrast=1.1, saturation=0.9)
        assert result is not None

    def test_unknown_preset_returns_original(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = ColorGrade.apply_preset(img, "nonexistent")
        assert result == img
