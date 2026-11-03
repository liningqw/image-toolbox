"""命令行入口：解析参数、调度功能、统一处理错误。"""

from __future__ import annotations

import argparse
import sys

from PIL import Image

from . import __version__
from .errors import ImageToolError
from .image_io import (
    EXTENSIONS,
    SAVE_FORMATS,
    load_image,
    normalize_format,
    resolve_output,
    save_image,
    source_format,
)
from .info import collect_info, format_info
from .operations import (
    crop_image,
    flip_image,
    grayscale_image,
    resize_image,
    rotate_image,
)

# 输出给用户的提示中不需要再出现 Pillow 的 "Transpose" 之类细节
_ALPHA_TIP = "提示：原图带透明通道，目标格式不支持透明，已自动合成到白色背景。"


def _default_format(image: Image.Image) -> str:
    """默认沿用原图格式；不支持的格式（如 GIF）统一保存为 PNG。"""
    fmt = source_format(image)
    return fmt if fmt in SAVE_FORMATS else "PNG"


def _save_result(
    image: Image.Image,
    source: str,
    output: str | None,
    suffix: str,
    fmt: str,
) -> None:
    """保存结果并打印保存位置。"""
    out = resolve_output(source, output, suffix, EXTENSIONS[fmt])
    flattened = save_image(image, out, fmt)
    if flattened:
        print(_ALPHA_TIP)
    print(f"已保存：{out.resolve()}")


def cmd_info(args: argparse.Namespace) -> int:
    """imgtool info：显示图片基础信息。"""
    print(format_info(collect_info(args.image)))
    return 0


def cmd_resize(args: argparse.Namespace) -> int:
    """imgtool resize：缩放图片。"""
    image = load_image(args.image)
    result = resize_image(image, args.width, args.height)
    _save_result(result, args.image, args.output, "resized", _default_format(image))
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    """imgtool crop：裁剪图片。"""
    image = load_image(args.image)
    result = crop_image(image, args.left, args.top, args.right, args.bottom)
    _save_result(result, args.image, args.output, "cropped", _default_format(image))
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """imgtool rotate：旋转图片。"""
    image = load_image(args.image)
    result = rotate_image(image, args.angle)
    _save_result(
        result,
        args.image,
        args.output,
        f"rotated{args.angle}",
        _default_format(image),
    )
    return 0


def cmd_flip(args: argparse.Namespace) -> int:
    """imgtool flip：水平 / 垂直翻转。"""
    image = load_image(args.image)
    result = flip_image(image, args.direction)
    _save_result(
        result,
        args.image,
        args.output,
        f"flipped_{args.direction}",
        _default_format(image),
    )
    return 0


def cmd_gray(args: argparse.Namespace) -> int:
    """imgtool gray：转灰度图。"""
    image = load_image(args.image)
    result = grayscale_image(image)
    _save_result(result, args.image, args.output, "gray", _default_format(image))
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """imgtool convert：格式转换。"""
    image = load_image(args.image)
    fmt = normalize_format(args.format)
    _save_result(image, args.image, args.output, "converted", fmt)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """创建命令行解析器。"""
    parser = argparse.ArgumentParser(
        prog="imgtool",
        description="一个简单的命令行图片工具：查看图片信息，并进行缩放、裁剪、旋转、翻转、灰度化和格式转换。",
        epilog=(
            "示例：\n"
            "  python -m imgtool info examples/sample.png\n"
            "  python -m imgtool resize examples/sample.png --width 160\n"
            "  python -m imgtool gray examples/sample.png -o examples/output/sample_gray.png\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="命令")

    p_info = sub.add_parser("info", help="查看图片基础信息")
    p_info.add_argument("image", help="图片路径")
    p_info.set_defaults(func=cmd_info)

    p_resize = sub.add_parser("resize", help="缩放图片")
    p_resize.add_argument("image", help="图片路径")
    p_resize.add_argument("--width", type=int, help="目标宽度（像素，>0）")
    p_resize.add_argument("--height", type=int, help="目标高度（像素，>0）")
    p_resize.add_argument("-o", "--output", help="输出文件路径，默认在原图旁生成 <原名>_resized.<扩展名>")
    p_resize.set_defaults(func=cmd_resize)

    p_crop = sub.add_parser("crop", help="裁剪图片")
    p_crop.add_argument("image", help="图片路径")
    p_crop.add_argument("--left", type=int, required=True, help="裁剪区域左边界（像素）")
    p_crop.add_argument("--top", type=int, required=True, help="裁剪区域上边界（像素）")
    p_crop.add_argument("--right", type=int, required=True, help="裁剪区域右边界（像素，不含）")
    p_crop.add_argument("--bottom", type=int, required=True, help="裁剪区域下边界（像素，不含）")
    p_crop.add_argument("-o", "--output", help="输出文件路径，默认生成 <原名>_cropped.<扩展名>")
    p_crop.set_defaults(func=cmd_crop)

    p_rotate = sub.add_parser("rotate", help="旋转图片（逆时针）")
    p_rotate.add_argument("image", help="图片路径")
    p_rotate.add_argument("--angle", type=int, required=True, help="旋转角度，支持 90、180、270")
    p_rotate.add_argument("-o", "--output", help="输出文件路径，默认生成 <原名>_rotated<角度>.<扩展名>")
    p_rotate.set_defaults(func=cmd_rotate)

    p_flip = sub.add_parser("flip", help="翻转图片")
    p_flip.add_argument("image", help="图片路径")
    p_flip.add_argument(
        "--direction",
        required=True,
        choices=("horizontal", "vertical"),
        help="翻转方向：horizontal（水平）或 vertical（垂直）",
    )
    p_flip.add_argument("-o", "--output", help="输出文件路径，默认生成 <原名>_flipped_<方向>.<扩展名>")
    p_flip.set_defaults(func=cmd_flip)

    p_gray = sub.add_parser("gray", help="转换为灰度图")
    p_gray.add_argument("image", help="图片路径")
    p_gray.add_argument("-o", "--output", help="输出文件路径，默认生成 <原名>_gray.<扩展名>")
    p_gray.set_defaults(func=cmd_gray)

    p_convert = sub.add_parser("convert", help="转换图片格式")
    p_convert.add_argument("image", help="图片路径")
    p_convert.add_argument(
        "--format",
        required=True,
        choices=("png", "jpg", "jpeg", "bmp", "webp"),
        help="目标格式",
    )
    p_convert.add_argument("-o", "--output", help="输出文件路径，默认生成 <原名>_converted.<目标扩展名>")
    p_convert.set_defaults(func=cmd_convert)

    return parser


def main(argv: list[str] | None = None) -> int:
    """程序入口，返回进程退出码。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except ImageToolError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
