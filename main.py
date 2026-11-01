# -*- coding: utf-8 -*-
"""程序入口：单实例、托盘常驻、全局热键呼出。

用 python main.py 直接运行，或用 build.py 打包成 EXE。
"""

import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app import config as cfgmod  # noqa: E402
from app import theme  # noqa: E402
from app.controller import Controller  # noqa: E402

SERVER_NAME = "QuickDial.SingleInstance.v1"


def _log_exception(exc_type, exc_value, exc_tb):
    """未捕获异常写入日志，避免无提示闪退。"""
    try:
        path = os.path.join(cfgmod.config_dir(), "error.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("----- " + __import__("datetime").datetime.now().isoformat() + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _notify_existing():
    """已有实例在跑：通知它弹出设置窗口，然后本进程退出。"""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(400):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return True
    return False


def _start_server(app, controller):
    server = QLocalServer(app)
    server.removeServer(SERVER_NAME)
    if not server.listen(SERVER_NAME):
        return None

    def on_new_connection():
        while server.hasPendingConnections():
            conn = server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: _handle(controller, c))
            conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(on_new_connection)
    return server


def _handle(controller, conn):
    data = bytes(conn.readAll())
    if b"show" in data:
        controller.show_settings()


def main():
    sys.excepthook = _log_exception

    if _notify_existing():
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("QuickDial")
    app.setApplicationDisplayName("快捷转盘")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(theme.app_stylesheet())

    first_run = not os.path.exists(cfgmod.config_path())

    controller = Controller(app)
    if not controller.start():
        QMessageBox.critical(
            None,
            "启动失败",
            "无法安装全局键盘钩子。\n可能被安全软件拦截，请尝试以管理员身份运行。",
        )
        return 1

    _start_server(app, controller)

    if first_run:
        controller.show_settings()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
