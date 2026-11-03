"""核心图片操作与读写的单元测试。"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from imgtool.errors import ImageToolError
from imgtool.image_io import flatten_alpha, load_image, save_image
from imgtool.info import collect_info, format_file_size
from imgtool.operations import (
    crop_image,
    flip_image,
    grayscale_image,
    resize_image,
    rotate_image,
)


def make_image(size=(200, 100), color=(255, 0, 0, 255), mode="RGBA") -> Image.Image:
    return Image.new(mode, size, color)


class ResizeTest(unittest.TestCase):
    def test_resize_by_width_keeps_ratio(self):
        result = resize_image(make_image((200, 100)), width=50)
        self.assertEqual(result.size, (50, 25))

    def test_resize_by_height_keeps_ratio(self):
        result = resize_image(make_image((200, 100)), height=300)
        self.assertEqual(result.size, (600, 300))

    def test_resize_with_both_sides_exact(self):
        result = resize_image(make_image((200, 100)), width=123, height=45)
        self.assertEqual(result.size, (123, 45))

    def test_resize_requires_a_side(self):
        with self.assertRaises(ImageToolError):
            resize_image(make_image())

    def test_resize_rejects_non_positive(self):
        with self.assertRaises(ImageToolError):
            resize_image(make_image(), width=0)
        with self.assertRaises(ImageToolError):
            resize_image(make_image(), height=-5)


class CropTest(unittest.TestCase):
    def test_crop_returns_region(self):
        result = crop_image(make_image((100, 80)), left=10, top=10, right=60, bottom=50)
        self.assertEqual(result.size, (50, 40))

    def test_crop_out_of_bounds(self):
        image = make_image((100, 80))
        with self.assertRaises(ImageToolError):
            crop_image(image, 0, 0, 101, 80)
        with self.assertRaises(ImageToolError):
            crop_image(image, -1, 0, 50, 50)
        with self.assertRaises(ImageToolError):
            crop_image(image, 0, 0, 50, 81)

    def test_crop_invalid_order(self):
        with self.assertRaises(ImageToolError):
            crop_image(make_image((100, 80)), 50, 10, 50, 40)
        with self.assertRaises(ImageToolError):
            crop_image(make_image((100, 80)), 10, 40, 50, 40)


class RotateFlipTest(unittest.TestCase):
    def test_rotate_90_swaps_size(self):
        self.assertEqual(rotate_image(make_image((100, 50)), 90).size, (50, 100))
        self.assertEqual(rotate_image(make_image((100, 50)), 180).size, (100, 50))
        self.assertEqual(rotate_image(make_image((100, 50)), 270).size, (50, 100))

    def test_rotate_rejects_other_angles(self):
        with self.assertRaises(ImageToolError):
            rotate_image(make_image(), 45)

    def test_flip_horizontal_moves_pixels(self):
        image = make_image((2, 1), (255, 0, 0, 255))
        image.putpixel((1, 0), (0, 0, 255, 255))
        result = flip_image(image, "horizontal")
        self.assertEqual(result.getpixel((0, 0))[0], 0)
        self.assertEqual(result.getpixel((0, 0))[2], 255)

    def test_flip_rejects_unknown_direction(self):
        with self.assertRaises(ImageToolError):
            flip_image(make_image(), "diagonal")


class GrayscaleTest(unittest.TestCase):
    def test_gray_mode_and_value(self):
        result = grayscale_image(make_image((10, 10), (255, 0, 0, 255)))
        self.assertEqual(result.mode, "L")
        self.assertLess(result.getpixel((0, 0)), 100)


class InfoTest(unittest.TestCase):
    def test_collect_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.png"
            make_image((320, 240)).save(path)
            info = collect_info(path)
            self.assertEqual(info.filename, "demo.png")
            self.assertEqual((info.width, info.height), (320, 240))
            self.assertEqual(info.mode, "RGBA")
            self.assertTrue(info.alpha)
            self.assertGreater(info.file_size, 0)

    def test_format_file_size(self):
        self.assertEqual(format_file_size(512), "0.50 KB")
        self.assertEqual(format_file_size(1536), "1.50 KB")
        self.assertEqual(format_file_size(3 * 1024 * 1024), "3.00 MB")


class SaveTest(unittest.TestCase):
    def test_save_jpg_flattens_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jpg"
            image = Image.new("RGBA", (10, 10), (255, 0, 0, 0))
            flattened = save_image(image, out, "JPEG")
            self.assertTrue(flattened)
            with Image.open(out) as saved:
                self.assertEqual(saved.mode, "RGB")
                # 完全透明的区域被合成到白色背景上
                self.assertGreater(saved.getpixel((0, 0))[0], 250)

    def test_save_png_keeps_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.png"
            image = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
            flattened = save_image(image, out, "PNG")
            self.assertFalse(flattened)
            with Image.open(out) as saved:
                self.assertEqual(saved.mode, "RGBA")

    def test_load_invalid_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.jpg"
            path.write_text("this is not an image", encoding="utf-8")
            with self.assertRaises(ImageToolError):
                load_image(path)

    def test_flatten_alpha_returns_rgb(self):
        result = flatten_alpha(Image.new("RGBA", (5, 5), (0, 0, 0, 0)))
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
