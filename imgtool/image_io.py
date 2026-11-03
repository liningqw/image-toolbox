"""图片读写相关的公共函数：加载、保存、输出路径处理。

所有文件操作都集中在这里，方便统一处理错误和透明通道。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .errors import ImageToolError

# 程序支持保存的格式，以及各自对应的扩展名
SAVE_FORMATS = ("PNG", "JPEG", "BMP", "WEBP")
EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "WEBP": ".webp"}

# 这些格式不支持透明通道，保存前需要先把透明通道压到白色背景上
NO_ALPHA_FORMATS = {"JPEG", "BMP"}

FORMAT_LABELS = {
    "PNG": "PNG",
    "JPEG": "JPEG",
    "BMP": "BMP",
    "WEBP": "WebP",
    "GIF": "GIF",
    "TIFF": "TIFF",
}

MODE_LABELS = {
    "1": "二值图",
    "L": "灰度",
    "LA": "灰度 + 透明通道",
    "P": "调色板",
    "RGB": "RGB",
    "RGBA": "RGBA（带透明通道）",
    "CMYK": "CMYK",
    "YCbCr": "YCbCr",
    "I": "32 位整数",
    "F": "32 位浮点",
}


def normalize_format(fmt: str) -> str:
    """把 jpg / JPG / jpeg 之类的写法统一成 Pillow 使用的格式名。"""
    fmt = fmt.strip().upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in SAVE_FORMATS:
        supported = "、".join(SAVE_FORMATS)
        raise ImageToolError(f"不支持保存为 {fmt} 格式，当前支持：{supported}。")
    return fmt


def load_image(path: str | Path) -> Image.Image:
    """读取图片，失败时抛出带中文说明的 ImageToolError。"""
    p = Path(path)
    if not p.exists():
        raise ImageToolError(f"文件不存在：{p}")
    if not p.is_file():
        raise ImageToolError(f"这不是一个文件：{p}")

    try:
        image = Image.open(p)
        # Image.open 是惰性的，必须 load 一次才能真正解码并发现损坏
        image.load()
    except UnidentifiedImageError:
        raise ImageToolError(f"不是有效的图片文件：{p}") from None
    except OSError as exc:
        raise ImageToolError(f"图片无法读取，文件可能已损坏：{p}（{exc}）") from None
    return image


def has_alpha(image: Image.Image) -> bool:
    """判断图片是否带有透明通道。"""
    if image.mode in ("RGBA", "LA"):
        return True
    # 调色板图片可能通过 info["transparency"] 指定透明色
    return image.mode == "P" and "transparency" in image.info


def flatten_alpha(image: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """把带透明通道的图片合成到纯色背景上，返回 RGB 图片。"""
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, background)
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    return canvas


def _prepare_for_save(image: Image.Image, fmt: str) -> tuple[Image.Image, bool]:
    """保存前按目标格式调整颜色模式，返回（处理后的图片, 是否压平了透明通道）。"""
    if fmt in NO_ALPHA_FORMATS:
        if has_alpha(image):
            return flatten_alpha(image), True
        if image.mode not in ("RGB", "L"):
            # 例如 P / CMYK 模式，转成 RGB 后才能稳定保存
            return image.convert("RGB"), False
        return image, False

    # PNG / WebP 支持透明通道，原样保存即可
    return image, False


def save_image(image: Image.Image, output_path: str | Path, fmt: str) -> bool:
    """保存图片，返回是否因为格式不支持而压平了透明通道。"""
    fmt = normalize_format(fmt)
    out = Path(output_path)
    prepared, flattened = _prepare_for_save(image, fmt)

    save_kwargs: dict = {}
    if fmt == "JPEG":
        save_kwargs = {"quality": 95, "optimize": True}
    elif fmt == "PNG":
        save_kwargs = {"optimize": True}

    try:
        prepared.save(out, format=fmt, **save_kwargs)
    except OSError as exc:
        raise ImageToolError(f"保存失败：{out}（{exc}）") from None
    return flattened


def source_format(image: Image.Image) -> str:
    """获取图片原始格式名（无法识别时默认 PNG）。"""
    fmt = (image.format or "PNG").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    return fmt


def resolve_output(
    input_path: str | Path,
    output: str | None,
    suffix: str,
    ext: str,
) -> Path:
    """计算输出文件路径，并做基本校验。

    默认输出到原图所在目录，文件名追加操作后缀，例如 demo_resized.png，
    从而保证永远不会覆盖原图。
    """
    src = Path(input_path)

    if output:
        out = Path(output)
        if out.suffix == "":
            out = out.with_suffix(ext)
    else:
        out = src.with_name(f"{src.stem}_{suffix}{ext}")

    if out.resolve() == src.resolve():
        raise ImageToolError("输出文件不能与原图相同，请换一个输出路径。")
    if out.is_dir():
        raise ImageToolError(f"输出路径是一个目录，请给出文件名：{out}")
    if not out.parent.exists():
        raise ImageToolError(f"输出目录不存在：{out.parent}")

    return out
