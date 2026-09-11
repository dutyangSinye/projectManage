"""pytest 全局配置。

关键点：`app/db/session.py` 在 **import 时**就按 `DATABASE_URL` 绑定了 engine，
兜底值是 `backend/data/workhours.db`（本地开发库）。如果测试模块先于环境变量导入应用代码，
测试写入就会落到开发库里。

这里在 pytest 收集测试用例 **之前** 先把 `DATABASE_URL` 钉到一次性临时库，
保证任何走 `app.*` 的测试都不可能碰到开发库。
"""

import os
import tempfile
from pathlib import Path

_SESSION_TEMP_DIR = tempfile.TemporaryDirectory(prefix="xinye-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_SESSION_TEMP_DIR.name) / 'tests.db'}"
os.environ["FEISHU_MODE"] = "mock"
os.environ["SYSTEM_ADMIN_USER_IDS"] = "1"
