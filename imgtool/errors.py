"""自定义异常。

程序把所有「用户可预期」的错误（文件不存在、图片无效、参数越界等）
都转换成 ImageToolError，由命令行入口统一捕获并打印友好提示，
避免用户看到一堆 traceback。
"""


class ImageToolError(Exception):
    """可预期的用户输入错误。"""
