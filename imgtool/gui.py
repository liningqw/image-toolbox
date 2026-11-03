"""图形界面版本：把 imgtool 做成一个 Windows 桌面上直接使用的小应用。

运行方式：
    python -m imgtool.gui
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk
from PIL import __version__ as PILLOW_VERSION

from . import __version__
from .errors import ImageToolError
from .image_io import (
    EXTENSIONS,
    SAVE_FORMATS,
    has_alpha,
    load_image,
    normalize_format,
    save_image,
    source_format,
)
from .info import format_file_size
from .operations import (
    crop_image,
    flip_image,
    grayscale_image,
    resize_image,
    rotate_image,
)

APP_NAME = "图片小工具"
BASE_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = BASE_DIR / "assets" / "app.ico"

PREVIEW_BG = "#f4f5f8"
CHECKER_COLORS = ("#ffffff", "#e7e9ee")
_FONT = ("Microsoft YaHei UI", 10)
_TITLE_FONT = ("Microsoft YaHei UI", 13, "bold")

_MODE_LABELS = {
    "1": "二值图",
    "L": "灰度",
    "LA": "灰度 · 含透明",
    "P": "调色板",
    "RGB": "RGB",
    "RGBA": "RGBA · 含透明",
    "CMYK": "CMYK",
    "I": "32 位整数",
    "F": "32 位浮点",
}

_CHECKER_CACHE: dict[tuple[int, int], Image.Image] = {}


def _checkerboard(size: tuple[int, int]) -> Image.Image:
    """生成透明背景用的灰白棋盘格。"""
    if size in _CHECKER_CACHE:
        return _CHECKER_CACHE[size]

    width, height = size
    image = Image.new("RGB", size, CHECKER_COLORS[0])
    draw = ImageDraw.Draw(image)
    cell = 14
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=CHECKER_COLORS[1])

    _CHECKER_CACHE[size] = image
    return image


class ImageToolApp(tk.Tk):
    """主窗口。"""

    def __init__(self) -> None:
        super().__init__()

        # 当前图片状态：original 永远保留刚打开时的样子，用于撤销
        self.original: Image.Image | None = None
        self.current: Image.Image | None = None
        self.image_path: Path | None = None
        self.dirty = False

        self._preview_ref: ImageTk.PhotoImage | None = None
        self._resize_job: str | None = None

        self._setup_window()
        self._setup_style()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._set_empty_state()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ 界面搭建

    def _setup_window(self) -> None:
        self.title(APP_NAME)
        self.configure(bg="#eef0f4")

        try:
            self.tk.call("tk", "scaling", self.winfo_fpixels("1i") / 72.0)
        except tk.TclError:
            pass

        if ICON_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except tk.TclError:
                pass

        # 按屏幕 DPI 放大窗口，避免字体变大后内容显示不全
        self._scale = min(max(self.winfo_fpixels("1i") / 96.0, 1.0), 1.75)
        scale = self._scale
        width = min(int(1120 * scale), self.winfo_screenwidth() - 80)
        height = min(int(760 * scale), self.winfo_screenheight() - 90)
        self.minsize(int(900 * scale), int(720 * scale))

        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        for theme in ("vista", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        style.configure(".", font=_FONT)
        style.configure("TButton", padding=6)
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=7)
        style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#7a7f89")
        style.configure("Value.TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=_TITLE_FONT)
        style.configure("Toolbar.TFrame", background="#eef0f4")
        style.configure(
            "TNotebook.Tab",
            padding=(int(14 * self._scale), int(6 * self._scale)),
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="打开图片…", accelerator="Ctrl+O", command=self.open_image)
        file_menu.add_command(label="另存为…", accelerator="Ctrl+S", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="撤销全部修改", accelerator="Ctrl+Z", command=self.undo_all)
        menubar.add_cascade(label="编辑", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="使用说明", accelerator="F1", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.configure(menu=menubar)

    def _build_layout(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        main = ttk.Frame(self, padding=14)
        main.grid(row=0, column=0, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0, minsize=int(380 * self._scale))

        self._build_left(main)
        self._build_right(main)

        self.status_var = tk.StringVar(value="就绪：点击「打开图片」选择一张图片")
        status = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg="#e3e6eb",
            fg="#3f444c",
            padx=14,
            pady=6,
            font=_FONT,
        )
        status.grid(row=1, column=0, sticky="ew")

    def _build_left(self, parent: ttk.Frame) -> None:
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(left, style="Toolbar.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(toolbar, text="打开图片", style="Primary.TButton", command=self.open_image).pack(side="left")
        ttk.Button(toolbar, text="撤销修改", command=self.undo_all).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="另存为…", command=self.save_as).pack(side="left", padx=(8, 0))
        ttk.Label(
            toolbar,
            text="PNG / JPG / BMP / WebP",
            style="Hint.TLabel",
        ).pack(side="right")

        canvas_wrap = tk.Frame(left, bg="#d7dae0", bd=0, highlightthickness=0)
        canvas_wrap.grid(row=1, column=0, sticky="nsew")
        canvas_wrap.rowconfigure(0, weight=1)
        canvas_wrap.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_wrap,
            bg=PREVIEW_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_right(self, parent: ttk.Frame) -> None:
        right = ttk.Frame(parent, width=int(380 * self._scale))
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        info = ttk.LabelFrame(right, text=" 图片信息 ", padding=12)
        info.grid(row=0, column=0, sticky="ew")
        info.columnconfigure(1, weight=1)

        self.var_name = tk.StringVar(value="-")
        self.var_format = tk.StringVar(value="-")
        self.var_size = tk.StringVar(value="-")
        self.var_mode = tk.StringVar(value="-")
        self.var_bytes = tk.StringVar(value="-")

        rows = (
            ("文件名", self.var_name),
            ("格式", self.var_format),
            ("尺寸", self.var_size),
            ("颜色模式", self.var_mode),
            ("文件大小", self.var_bytes),
        )
        for index, (label, var) in enumerate(rows):
            ttk.Label(info, text=label, style="Hint.TLabel").grid(
                row=index, column=0, sticky="w", pady=3
            )
            ttk.Label(
                info,
                textvariable=var,
                style="Value.TLabel",
                anchor="e",
                justify="right",
                wraplength=int(240 * self._scale),
            ).grid(row=index, column=1, sticky="e", pady=3, padx=(10, 0))

        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        self._build_tab_adjust(self.notebook)
        self._build_tab_transform(self.notebook)
        self._build_tab_export(self.notebook)

    def _build_tab_adjust(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text="缩放 / 裁剪")
        tab.columnconfigure(0, weight=1)

        resize_box = ttk.LabelFrame(tab, text=" 缩放 ", padding=12)
        resize_box.grid(row=0, column=0, sticky="ew")
        resize_box.columnconfigure(1, weight=1)

        self.width_var = tk.StringVar()
        self.height_var = tk.StringVar()

        ttk.Label(resize_box, text="宽度").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(resize_box, textvariable=self.width_var, width=10).grid(
            row=0, column=1, sticky="ew", padx=(10, 4), pady=3
        )
        ttk.Label(resize_box, text="像素").grid(row=0, column=2, sticky="w", pady=3)

        ttk.Label(resize_box, text="高度").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(resize_box, textvariable=self.height_var, width=10).grid(
            row=1, column=1, sticky="ew", padx=(10, 4), pady=3
        )
        ttk.Label(resize_box, text="像素").grid(row=1, column=2, sticky="w", pady=3)

        ttk.Label(
            resize_box,
            text="只填一项时按原图比例缩放；两项都填则缩放到指定尺寸。",
            style="Hint.TLabel",
            wraplength=int(300 * self._scale),
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 8))

        ttk.Button(resize_box, text="应用缩放", command=self.apply_resize).grid(
            row=3, column=0, columnspan=3, sticky="ew"
        )

        crop_box = ttk.LabelFrame(tab, text=" 裁剪 ", padding=12)
        crop_box.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        for column in (1, 3):
            crop_box.columnconfigure(column, weight=1)

        self.crop_left_var = tk.StringVar()
        self.crop_top_var = tk.StringVar()
        self.crop_right_var = tk.StringVar()
        self.crop_bottom_var = tk.StringVar()

        crop_fields = (
            ("左", self.crop_left_var, 0, 0),
            ("上", self.crop_top_var, 0, 2),
            ("右", self.crop_right_var, 1, 0),
            ("下", self.crop_bottom_var, 1, 2),
        )
        for label, var, row, column in crop_fields:
            ttk.Label(crop_box, text=label).grid(
                row=row, column=column, sticky="w", pady=3
            )
            ttk.Entry(crop_box, textvariable=var, width=8).grid(
                row=row, column=column + 1, sticky="ew", padx=(6, 12), pady=3
            )

        ttk.Label(
            crop_box,
            text="坐标单位为像素，右/下边界不包含在裁剪区域内。",
            style="Hint.TLabel",
            wraplength=int(300 * self._scale),
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 8))

        ttk.Button(crop_box, text="应用裁剪", command=self.apply_crop).grid(
            row=3, column=0, columnspan=4, sticky="ew"
        )

    def _build_tab_transform(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text="旋转 / 翻转")
        tab.columnconfigure(0, weight=1)

        rotate_box = ttk.LabelFrame(tab, text=" 旋转（逆时针） ", padding=12)
        rotate_box.grid(row=0, column=0, sticky="ew")
        for index in range(3):
            rotate_box.columnconfigure(index, weight=1)
        for index, angle in enumerate((90, 180, 270)):
            ttk.Button(
                rotate_box,
                text=f"{angle}°",
                command=lambda value=angle: self.apply_rotate(value),
            ).grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 6, 0))

        flip_box = ttk.LabelFrame(tab, text=" 翻转 ", padding=12)
        flip_box.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        flip_box.columnconfigure(0, weight=1)
        flip_box.columnconfigure(1, weight=1)
        ttk.Button(flip_box, text="水平翻转", command=lambda: self.apply_flip("horizontal")).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(flip_box, text="垂直翻转", command=lambda: self.apply_flip("vertical")).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        gray_box = ttk.LabelFrame(tab, text=" 颜色 ", padding=12)
        gray_box.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        gray_box.columnconfigure(0, weight=1)
        ttk.Label(
            gray_box,
            text="把彩色图片转换为灰度图。",
            style="Hint.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Button(gray_box, text="转换为灰度图", command=self.apply_gray).grid(
            row=1, column=0, sticky="ew"
        )

    def _build_tab_export(self, notebook: ttk.Notebook) -> None:
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text="导出")
        tab.columnconfigure(0, weight=1)

        export_box = ttk.LabelFrame(tab, text=" 保存设置 ", padding=12)
        export_box.grid(row=0, column=0, sticky="ew")
        export_box.columnconfigure(1, weight=1)

        self.format_var = tk.StringVar(value="PNG")
        ttk.Label(export_box, text="保存格式").grid(row=0, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(
            export_box,
            textvariable=self.format_var,
            values=list(SAVE_FORMATS),
            state="readonly",
            width=10,
        )
        combo.grid(row=0, column=1, sticky="e", pady=4)

        ttk.Label(
            export_box,
            text="结果会保存为新文件，不会覆盖原图。\nJPG / BMP 不支持透明通道，会自动使用白色背景。",
            style="Hint.TLabel",
            wraplength=int(300 * self._scale),
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 10))

        ttk.Button(
            export_box,
            text="另存为…",
            style="Primary.TButton",
            command=self.save_as,
        ).grid(row=2, column=0, columnspan=2, sticky="ew")

        tip = ttk.LabelFrame(tab, text=" 小提示 ", padding=12)
        tip.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(
            tip,
            text="所有操作都只修改内存中的预览图，\n点击「撤销修改」可以随时恢复原图。",
            style="Hint.TLabel",
            justify="left",
        ).pack(anchor="w")

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-o>", lambda _event: self.open_image())
        self.bind("<Control-s>", lambda _event: self.save_as())
        self.bind("<Control-z>", lambda _event: self.undo_all())
        self.bind("<F1>", lambda _event: self.show_help())

    # ------------------------------------------------------------------ 图片状态

    def _set_empty_state(self) -> None:
        for var in (self.var_name, self.var_format, self.var_size, self.var_mode, self.var_bytes):
            var.set("-")
        self.canvas.delete("all")
        self.canvas.create_text(
            max(self.canvas.winfo_width(), 400) // 2,
            max(self.canvas.winfo_height(), 300) // 2,
            text="打开一张图片开始\n\n支持 PNG / JPG / BMP / WebP",
            fill="#9aa0aa",
            font=("Microsoft YaHei UI", 13),
            justify="center",
        )

    def status(self, text: str) -> None:
        self.status_var.set(text)

    def _update_info(self) -> None:
        if self.image_path is None or self.current is None:
            self._set_empty_state()
            return

        suffix = "（已修改）" if self.dirty else ""
        self.var_name.set(f"{self.image_path.name}{suffix}")
        fmt = source_format(self.original) if self.original else "PNG"
        self.var_format.set(fmt)
        self.var_size.set(f"{self.current.width} × {self.current.height} 像素")
        self.var_mode.set(_MODE_LABELS.get(self.current.mode, self.current.mode))
        try:
            self.var_bytes.set(format_file_size(self.image_path.stat().st_size))
        except OSError:
            self.var_bytes.set("-")

    def _sync_operation_fields(self, reset_format: bool = False) -> None:
        if self.current is None:
            return
        self.width_var.set(str(self.current.width))
        self.height_var.set(str(self.current.height))
        self.crop_left_var.set("0")
        self.crop_top_var.set("0")
        self.crop_right_var.set(str(self.current.width))
        self.crop_bottom_var.set(str(self.current.height))

        if reset_format:
            fmt = source_format(self.original) if self.original else "PNG"
            self.format_var.set(fmt if fmt in SAVE_FORMATS else "PNG")

    def load_path(self, path: str | Path) -> None:
        """加载指定图片（也供自动化测试调用）。"""
        try:
            image = load_image(path)
        except ImageToolError as exc:
            messagebox.showerror("无法打开图片", str(exc), parent=self)
            return

        self.image_path = Path(path)
        self.original = image.copy()
        self.current = image
        self.dirty = False
        self._sync_operation_fields(reset_format=True)
        self._update_info()
        self._render_preview()
        self.title(f"{APP_NAME} - {self.image_path.name}")
        self.status(f"已打开：{self.image_path}")

    def open_image(self) -> None:
        if self.dirty and not messagebox.askyesno(
            "未保存的修改", "当前图片有未保存的修改，仍要打开其他图片吗？", parent=self
        ):
            return

        path = filedialog.askopenfilename(
            parent=self,
            title="选择图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tif *.tiff"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.load_path(path)

    def _render_preview(self) -> None:
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 20 or height < 20:
            return

        if self.current is None:
            self._set_empty_state()
            return

        image = self.current
        ratio = min((width - 36) / image.width, (height - 36) / image.height, 4.0)
        ratio = max(ratio, 0.01)
        new_size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
        preview = image.resize(new_size, Image.Resampling.LANCZOS)
        if preview.mode not in ("L", "RGB", "RGBA"):
            preview = preview.convert("RGB")

        if has_alpha(preview):
            background = _checkerboard(new_size).convert("RGBA")
            if preview.mode != "RGBA":
                preview = preview.convert("RGBA")
            background.alpha_composite(preview)
            preview = background.convert("RGB")

        self._preview_ref = ImageTk.PhotoImage(preview)
        self.canvas.create_image(width // 2, height // 2, image=self._preview_ref)

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._render_preview)

    # ------------------------------------------------------------------ 操作

    def _apply(self, operation, success_message: str) -> None:
        if self.current is None:
            messagebox.showinfo("提示", "请先打开一张图片。", parent=self)
            return

        try:
            result = operation(self.current)
        except ImageToolError as exc:
            messagebox.showerror("操作失败", str(exc), parent=self)
            return
        except Exception as exc:  # 兜底，避免界面因意外异常直接卡死
            messagebox.showerror("操作失败", f"发生未预期的错误：{exc}", parent=self)
            return

        self.current = result
        self.dirty = True
        self._sync_operation_fields()
        self._update_info()
        self._render_preview()
        self.status(success_message)
        self.title(f"{APP_NAME} - {self.image_path.name} *" if self.image_path else APP_NAME)

    @staticmethod
    def _parse_int(text: str, label: str, required: bool = True) -> int | None:
        text = text.strip()
        if not text:
            if required:
                raise ImageToolError(f"请填写{label}。")
            return None
        try:
            return int(text)
        except ValueError:
            raise ImageToolError(f"{label}必须是整数。") from None

    def apply_resize(self) -> None:
        try:
            width = self._parse_int(self.width_var.get(), "宽度", required=False)
            height = self._parse_int(self.height_var.get(), "高度", required=False)
        except ImageToolError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self)
            return

        self._apply(
            lambda image: resize_image(image, width, height),
            f"已缩放为 {width or '按比例'} × {height or '按比例'}",
        )
        if self.current is not None:
            self.status(f"缩放完成：{self.current.width} × {self.current.height} 像素")

    def apply_crop(self) -> None:
        try:
            left = self._parse_int(self.crop_left_var.get(), "左边界")
            top = self._parse_int(self.crop_top_var.get(), "上边界")
            right = self._parse_int(self.crop_right_var.get(), "右边界")
            bottom = self._parse_int(self.crop_bottom_var.get(), "下边界")
        except ImageToolError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self)
            return

        self._apply(
            lambda image: crop_image(image, left, top, right, bottom),
            "裁剪完成",
        )
        if self.current is not None:
            self.status(f"裁剪完成：{self.current.width} × {self.current.height} 像素")

    def apply_rotate(self, angle: int) -> None:
        self._apply(lambda image: rotate_image(image, angle), f"已逆时针旋转 {angle}°")

    def apply_flip(self, direction: str) -> None:
        label = "水平" if direction == "horizontal" else "垂直"
        self._apply(lambda image: flip_image(image, direction), f"已{label}翻转")

    def apply_gray(self) -> None:
        self._apply(grayscale_image, "已转换为灰度图")

    def undo_all(self) -> None:
        if self.original is None:
            return
        self.current = self.original.copy()
        self.dirty = False
        self._sync_operation_fields()
        self._update_info()
        self._render_preview()
        self.title(f"{APP_NAME} - {self.image_path.name}" if self.image_path else APP_NAME)
        self.status("已恢复到刚打开时的状态")

    # ------------------------------------------------------------------ 保存

    def save_as(self) -> None:
        if self.current is None or self.image_path is None:
            messagebox.showinfo("提示", "请先打开一张图片。", parent=self)
            return

        try:
            fmt = normalize_format(self.format_var.get())
        except ImageToolError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return

        extension = EXTENSIONS[fmt]
        default_name = f"{self.image_path.stem}_edited{extension}"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="另存为",
            defaultextension=extension,
            initialfile=default_name,
            initialdir=str(self.image_path.parent),
            filetypes=[(f"{fmt} 图片", f"*{extension}"), ("所有文件", "*.*")],
        )
        if not path:
            return

        try:
            if Path(path).resolve() == self.image_path.resolve():
                raise ImageToolError("不能覆盖原图，请换一个文件名。")
            flattened = save_image(self.current, path, fmt)
        except ImageToolError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return

        message = f"已保存到：\n{path}"
        if flattened:
            message = "原图带透明通道，已自动合成到白色背景。\n\n" + message
        messagebox.showinfo("保存成功", message, parent=self)
        self.status(f"已保存：{path}")
        self.dirty = False
        self._update_info()
        self.title(f"{APP_NAME} - {self.image_path.name}")

    # ------------------------------------------------------------------ 其他

    def show_help(self) -> None:
        messagebox.showinfo(
            "使用说明",
            "1. 点击「打开图片」，选择一张图片。\n"
            "2. 在右侧标签页中缩放、裁剪、旋转、翻转或转换灰度。\n"
            "3. 在「导出」页选择格式，点击「另存为…」保存结果。\n\n"
            "所有操作都作用在内存中的图片上，不会改动原文件；\n"
            "点击「撤销修改」可以随时恢复原图。",
            parent=self,
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            "关于",
            f"{APP_NAME} v{__version__}\n\n"
            "基于 Python + Pillow + Tkinter 的本地图片小工具。\n"
            f"Pillow {PILLOW_VERSION}",
            parent=self,
        )

    def _on_close(self) -> None:
        if self.dirty and not messagebox.askyesno(
            "退出", "当前修改尚未保存，确定退出吗？", parent=self
        ):
            return
        self.destroy()


def _enable_high_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main() -> int:
    _enable_high_dpi()
    app = ImageToolApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
