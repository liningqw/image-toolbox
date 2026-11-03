"""读取并格式化图片基础信息。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .image_io import FORMAT_LABELS, MODE_LABELS, has_alpha, load_image


@dataclass(frozen=True)
class ImageInfo:
    """一张图片的基础信息。"""

    filename: str
    format: str
    width: int
    height: int
    mode: str
    file_size: int
    alpha: bool


def format_file_size(size: int) -> str:
    """把字节数格式化为保留两位小数的 KB / MB。"""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / 1024:.2f} KB"


def collect_info(path: str | Path) -> ImageInfo:
    """读取图片并收集信息。"""
    image: Image.Image = load_image(path)
    p = Path(path)
    return ImageInfo(
        filename=p.name,
        format=FORMAT_LABELS.get((image.format or "PNG").upper(), image.format or "未知"),
        width=image.width,
        height=image.height,
        mode=image.mode,
        file_size=p.stat().st_size,
        alpha=has_alpha(image),
    )


def format_info(info: ImageInfo) -> str:
    """把信息整理成便于阅读的多行文本。"""
    mode_label = MODE_LABELS.get(info.mode, info.mode)
    if info.alpha and "透明" not in mode_label:
        mode_label += "（带透明通道）"

    lines = [
        f"文件名：{info.filename}",
        f"图片格式：{info.format}",
        f"宽度 × 高度：{info.width} × {info.height} 像素",
        f"颜色模式：{mode_label}",
        f"文件大小：{format_file_size(info.file_size)}",
    ]
    return "\n".join(lines)
