"""图片编辑操作。

每个函数只负责一种编辑，接收 PIL.Image，返回新的 PIL.Image，
不修改传入的原图对象。
"""

from __future__ import annotations

from PIL import Image

from .errors import ImageToolError

# 旋转角度与 Pillow 转置操作的对应关系（逆时针）
_ROTATE_ACTIONS = {
    90: Image.Transpose.ROTATE_90,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_270,
}

# 翻转方向与 Pillow 转置操作的对应关系
_FLIP_ACTIONS = {
    "horizontal": Image.Transpose.FLIP_LEFT_RIGHT,
    "vertical": Image.Transpose.FLIP_TOP_BOTTOM,
}


def resize_image(
    image: Image.Image,
    width: int | None = None,
    height: int | None = None,
) -> Image.Image:
    """缩放图片。

    - 同时给出宽高：缩放到指定尺寸（可能变形）；
    - 只给宽度或高度：按原图比例缩放。
    """
    if width is None and height is None:
        raise ImageToolError("请至少指定 --width 或 --height 之一。")

    if width is not None and width <= 0:
        raise ImageToolError(f"宽度必须是大于 0 的整数，当前为 {width}。")
    if height is not None and height <= 0:
        raise ImageToolError(f"高度必须是大于 0 的整数，当前为 {height}。")

    old_w, old_h = image.size
    if width is not None and height is not None:
        new_size = (width, height)
    elif width is not None:
        new_size = (width, max(1, round(old_h * width / old_w)))
    else:
        new_size = (max(1, round(old_w * height / old_h)), height)

    return image.resize(new_size, Image.Resampling.LANCZOS)


def crop_image(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> Image.Image:
    """按左上角、右下角坐标裁剪图片，区域越界时给出明确提示。"""
    width, height = image.size

    if left < 0 or top < 0 or right > width or bottom > height:
        raise ImageToolError(
            f"裁剪区域越界：图片尺寸为 {width}×{height}，"
            f"裁剪区域为 left={left}, top={top}, right={right}, bottom={bottom}。"
        )
    if left >= right or top >= bottom:
        raise ImageToolError(
            f"裁剪区域无效：需要满足 left < right 且 top < bottom，"
            f"当前为 left={left}, top={top}, right={right}, bottom={bottom}。"
        )

    return image.crop((left, top, right, bottom))


def rotate_image(image: Image.Image, angle: int) -> Image.Image:
    """逆时针旋转图片，只接受 90、180、270 度。"""
    if angle not in _ROTATE_ACTIONS:
        raise ImageToolError(f"旋转角度只支持 90、180、270 度，当前为 {angle}。")
    return image.transpose(_ROTATE_ACTIONS[angle])


def flip_image(image: Image.Image, direction: str) -> Image.Image:
    """水平或垂直翻转。"""
    if direction not in _FLIP_ACTIONS:
        raise ImageToolError(
            f"翻转方向只支持 horizontal 或 vertical，当前为 {direction}。"
        )
    return image.transpose(_FLIP_ACTIONS[direction])


def grayscale_image(image: Image.Image) -> Image.Image:
    """把彩色图片转换为灰度图。"""
    return image.convert("L")
