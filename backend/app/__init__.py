"""
测试管理系统 - 主应用包

基于 BrowserStack Test Management API 设计的专业软件测试管理系统
使用 FastAPI + PostgreSQL + MongoDB 技术栈
"""

# ============================================================================
# 全局编码修复：强制 subprocess.Popen 在 text 模式下默认使用 UTF-8
# ============================================================================
# 中文 Windows 默认编码为 GBK，当子进程输出 UTF-8 字节时会抛出：
#   UnicodeDecodeError: 'gbk' codec can't decode byte ...
# deepagents 的 LocalShellBackend 调用 subprocess.run(text=True) 时未指定
# encoding，而 subprocess.run 底层使用 Popen，因此直接补丁 Popen.__init__
# 可以覆盖 run / Popen / check_output 等所有子进程创建路径。
# 必须在导入任何使用 subprocess 的模块前执行。

import subprocess

_original_popen_init = subprocess.Popen.__init__


def _popen_init_with_utf8(self, *args, **kwargs):
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _original_popen_init(self, *args, **kwargs)


subprocess.Popen.__init__ = _popen_init_with_utf8

# ============================================================================

from pathlib import Path
from dotenv import load_dotenv
# pragma: no cover  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2VEdVNGN3PT06YjYwOWE4Zjg=

# 加载项目根目录的 .env（与 start_server_postgres.py 共用）
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

__version__ = "1.0.0"
__author__ = "Test Management Team"

# 说明：deepagents 的 _messages_delta_reducer 对 state=None 崩溃的问题，
# 无法用 monkeypatch 修复——deepagents/__init__.py 急切导入 deepagents.graph，
# 后者在类定义时即把该函数按值绑定进 DeltaChannel，任何运行期替换都赶不上。
# 因此修复直接落在源文件 .venv/.../deepagents/_messages_reducer.py 中。
# 重新安装/升级 deepagents 后需重新应用该补丁（详见 README / 依赖说明）。

# pragma: no cover  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2VEdVNGN3PT06YjYwOWE4Zjg=
