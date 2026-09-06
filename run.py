"""PyInstaller 打包入口（项目根目录）。

原因：main.py 内部使用包相对导入（`from . import ...`），而 PyInstaller 会把
入口脚本视为顶层模块，相对导入会崩溃。本启动器先把 src 加入 sys.path，
再以完整包上下文导入 code_widget.main，两种运行方式都正确：

- 开发：cd src && python -m code_widget.main
- 打包：PyInstaller 以 run.py 为入口（见 DDRedeeMe.spec）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from code_widget.main import main

if __name__ == "__main__":
    raise SystemExit(main())
