"""开机自启动（F1）：写 HKCU Run 注册表，无需管理员。

- 打包(frozen)：注册 exe 自身路径；
- 开发模式：注册 pythonw + run.py（run.py 提供包上下文，直接跑 main.py
  会因相对导入崩溃——与打包入口同理）。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .. import APP_ID

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = APP_ID.split(".")[-1]   # "DDRedeeMe"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else python
    run_py = Path(__file__).resolve().parents[3] / "run.py"
    return f'"{exe}" "{run_py}"'


def is_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, APP_REG_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


def set_enabled(enable: bool) -> None:
    """enable=True 写注册表；False 删除键值（不存在则忽略）。失败抛 OSError。"""
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, APP_REG_NAME, 0, winreg.REG_SZ, _command())
            log.info("已开启开机自启动: %s", _command())
        else:
            try:
                winreg.DeleteValue(k, APP_REG_NAME)
                log.info("已关闭开机自启动")
            except FileNotFoundError:
                pass
