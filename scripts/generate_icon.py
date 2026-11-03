"""生成应用图标（PNG + 多尺寸 ICO）。"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def make_icon(size: int = 256) -> Image.Image:
    gradient = Image.new("RGB", (size, size))
    pixels = gradient.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            pixels[x, y] = (
                int(74 + (128 - 74) * t),
                int(108 + (86 - 108) * t),
                int(255),
            )

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [8, 8, size - 8, size - 8], radius=58, fill=255
    )

    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle(
        [46, 62, 210, 194], radius=16, outline=(255, 255, 255, 255), width=10
    )
    draw.ellipse([68, 84, 104, 120], fill=(255, 212, 94, 255))
    draw.polygon([(58, 184), (118, 122), (166, 184)], fill=(255, 255, 255, 255))
    draw.polygon([(132, 184), (176, 140), (206, 184)], fill=(214, 226, 255, 255))
    return icon


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    icon = make_icon(256)
    icon.save(ASSETS / "app.png")
    icon.save(
        ASSETS / "app.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"图标已生成：{ASSETS / 'app.ico'}")


if __name__ == "__main__":
    main()
