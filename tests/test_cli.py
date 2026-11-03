"""命令行入口的集成测试。"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from imgtool.cli import main


def run_cli(*argv: str) -> tuple[int, str, str]:
    """运行命令行，返回（退出码, 标准输出, 标准错误）。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.image = self.tmp / "demo.png"
        Image.new("RGBA", (120, 80), (20, 120, 220, 255)).save(self.image)

    def tearDown(self):
        self._tmp.cleanup()

    def test_info_prints_required_fields(self):
        code, out, _ = run_cli("info", str(self.image))
        self.assertEqual(code, 0)
        for text in ("文件名：demo.png", "图片格式：PNG", "120 × 80 像素", "颜色模式：RGBA", "文件大小："):
            self.assertIn(text, out)

    def test_resize_creates_new_file_and_keeps_original(self):
        before = self.image.read_bytes()
        code, out, _ = run_cli("resize", str(self.image), "--width", "60")
        self.assertEqual(code, 0)
        output = self.tmp / "demo_resized.png"
        self.assertTrue(output.exists())
        self.assertEqual(Image.open(output).size, (60, 40))
        self.assertEqual(self.image.read_bytes(), before, "原图不应该被修改")
        self.assertIn(str(output), out)

    def test_crop_out_of_bounds_reports_error(self):
        code, _, err = run_cli(
            "crop", str(self.image), "--left", "0", "--top", "0",
            "--right", "999", "--bottom", "999",
        )
        self.assertEqual(code, 2)
        self.assertIn("裁剪区域越界", err)

    def test_missing_file_reports_error(self):
        code, _, err = run_cli("info", str(self.tmp / "nope.png"))
        self.assertEqual(code, 2)
        self.assertIn("文件不存在", err)

    def test_invalid_image_reports_error(self):
        bad = self.tmp / "bad.jpg"
        bad.write_text("not an image", encoding="utf-8")
        code, _, err = run_cli("info", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("不是有效的图片文件", err)

    def test_refuses_to_overwrite_original(self):
        code, _, err = run_cli("resize", str(self.image), "--width", "10", "-o", str(self.image))
        self.assertEqual(code, 2)
        self.assertIn("不能与原图相同", err)

    def test_convert_png_to_jpg_flattens_alpha(self):
        code, out, _ = run_cli("convert", str(self.image), "--format", "jpg")
        self.assertEqual(code, 0)
        output = self.tmp / "demo_converted.jpg"
        self.assertTrue(output.exists())
        with Image.open(output) as saved:
            self.assertEqual(saved.mode, "RGB")
        self.assertIn("透明通道", out)

    def test_custom_output_path(self):
        output = self.tmp / "custom.png"
        code, _, _ = run_cli("gray", str(self.image), "-o", str(output))
        self.assertEqual(code, 0)
        with Image.open(output) as saved:
            self.assertEqual(saved.mode, "L")

    def test_invalid_angle_reports_error(self):
        code, _, err = run_cli("rotate", str(self.image), "--angle", "45")
        self.assertEqual(code, 2)
        self.assertIn("旋转角度只支持", err)


if __name__ == "__main__":
    unittest.main()
