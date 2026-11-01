# -*- coding: utf-8 -*-
"""一键打包脚本：pyinstaller 打包成单文件 EXE。

用法：
    .venv\\Scripts\\python.exe build.py
产物：
    dist\\快捷转盘.exe
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "快捷转盘"
ICON = os.path.join(ROOT, "assets", "app.ico")

EXCLUDES = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPdf",
    "PySide6.QtDBus",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtSvg",
    "PySide6.QtXml",
]


def _clean_workdir():
    """清掉旧的中间目录；失败不影响打包（某些受限环境禁止删除）。"""
    for name in ("build",):
        path = os.path.join(ROOT, name)
        if os.path.isdir(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError:
                pass


def main():
    _clean_workdir()

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        NAME,
        "--icon",
        ICON,
    ]
    for mod in EXCLUDES:
        args += ["--exclude-module", mod]
    args.append(os.path.join(ROOT, "main.py"))

    print("执行：", " ".join(args))
    ret = subprocess.call(args, cwd=ROOT)
    if ret != 0:
        print("打包失败，退出码", ret)
        return ret

    exe = os.path.join(ROOT, "dist", NAME + ".exe")
    if not os.path.exists(exe):
        print("未找到产物，请检查 PyInstaller 输出")
        return 1

    size = os.path.getsize(exe) / 1024 / 1024
    print("打包完成：%s（%.1f MB）" % (exe, size))

    # 清理中间产物（同上，失败不算错）
    try:
        _clean_workdir()
        spec = os.path.join(ROOT, NAME + ".spec")
        if os.path.exists(spec):
            os.remove(spec)
    except OSError as exc:
        print("清理中间产物时跳过：%s" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
