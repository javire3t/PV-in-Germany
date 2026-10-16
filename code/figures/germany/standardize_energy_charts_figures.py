"""Place the common EIFER title/source block inside supplied Energy-Charts figures.

The underlying chart pixels are retained.  Only the supplied installed-power
footer is removed; the common three-line block is then appended inside each
exported PNG.
"""

from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw, ImageFont

from project_paths import FINAL_OUTPUTS


RETRIEVED = "16.10.2026"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
DONUT_SOURCE = Path(r"C:\Users\Hawi\AppData\Local\Temp\codex-clipboard-ac87b178-df0f-4815-b470-690b8c8a23c2.png")
POWER_SOURCE = Path(r"C:\Users\Hawi\AppData\Local\Temp\codex-clipboard-b455da56-acf6-480e-9430-b3232444eebe.png")


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font, color: str, width: int) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill=color)


def _standardize(source: Path, output: Path, title: str, *, erase_bottom: int = 0) -> None:
    image = Image.open(source).convert("RGB")
    if erase_bottom:
        ImageDraw.Draw(image).rectangle(
            (0, image.height - erase_bottom, image.width, image.height), fill="white"
        )
    scale = image.width / 3600
    panel_height = round(360 * scale)
    canvas = Image.new("RGB", (image.width, image.height + panel_height), "white")
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(FONT_BOLD, round(88 * scale))
    detail_font = _font(FONT, round(60 * scale))
    top = image.height + round(38 * scale)
    _draw_centered(draw, title, top, title_font, "#17372C", canvas.width)
    _draw_centered(draw, "Visualization: EIFER", top + round(108 * scale), detail_font, "#666666", canvas.width)
    _draw_centered(draw, f"Data: Energy-Charts.info (retrieved {RETRIEVED})", top + round(180 * scale), detail_font, "#666666", canvas.width)
    canvas.save(output, quality=95)


def main() -> None:
    FINAL_OUTPUTS.mkdir(parents=True, exist_ok=True)
    _standardize(
        DONUT_SOURCE,
        FINAL_OUTPUTS / "Figure_electricity-mix_germany_497-5-TWh.png",
        "Electricity mix by source, Germany, 2025",
    )
    _standardize(
        POWER_SOURCE,
        FINAL_OUTPUTS / "Figure_installed-power_germany_2026.png",
        "Installed electricity capacity by technology, Germany, 2026",
        erase_bottom=130,
    )


if __name__ == "__main__":
    main()
