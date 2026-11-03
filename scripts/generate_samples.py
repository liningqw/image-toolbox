"""生成 README 中使用的示例图片（可重复运行）。"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def make_sample_png() -> None:
    """生成带透明通道的示例 PNG。"""
    width, height = 320, 240
    image = Image.new("RGBA", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            r = int(40 + 150 * x / width)
            g = int(90 + 60 * y / height)
            b = int(200 - 100 * y / height)
            pixels[x, y] = (r, g, b, 255)

    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 140, 140), fill=(255, 210, 60, 255))
    draw.rectangle((180, 70, 280, 170), fill=(230, 70, 90, 255))
    draw.polygon([(20, 220), (120, 150), (220, 220)], fill=(60, 200, 140, 255))

    # 左上角做透明渐变，用来演示透明通道
    for y in range(60):
        for x in range(60):
            alpha = min(255, int(255 * (x + y) / 118))
            r, g, b, _ = pixels[x, y]
            pixels[x, y] = (r, g, b, alpha)

    image.save(EXAMPLES / "sample.png")


def make_photo_jpg() -> None:
    """生成不带透明通道的示例 JPG。"""
    width, height = 400, 300
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                int(30 + 180 * y / height),
                int(120 + 90 * x / width),
                int(220 - 120 * y / height),
            )

    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 60, 180, 180), fill=(250, 240, 210))
    draw.rectangle((240, 90, 350, 200), fill=(40, 60, 120))
    image.save(EXAMPLES / "photo.jpg", quality=90)


def main() -> None:
    EXAMPLES.mkdir(exist_ok=True)
    make_sample_png()
    make_photo_jpg()
    print(f"示例图片已生成：{EXAMPLES}")


if __name__ == "__main__":
    main()
