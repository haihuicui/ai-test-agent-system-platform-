"""沙箱 L0 防回归测试。

三道防线：
1. 白名单内容金丝雀——build_script_exec_env/build_restricted_env 对敏感键零泄露，
   受控注入通道（extra_env）不受影响；
2. 静态防回归——执行点文件清单内禁止出现 ``os.environ.copy()`` / ``{**os.environ}``
   的全量继承写法（新执行点不加白名单就红）；
3. 看门狗行为——正常完成 / 内存超限熔断 / 超时 kill 三条路径。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.utils.proc_watchdog import run_cmd_with_watchdog
from app.utils.shell_env import build_restricted_env, build_script_exec_env

# 进程环境中最危险的密钥/凭据键（金丝雀清单，与 settings/.env 实际键对齐）
SENSITIVE_KEYS = [
    "DEEPSEEK_API_KEY",
    "POSTGRES_PASSWORD",
    "MONGODB_PASSWORD",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "MINIO_SECRET_KEY",
    "MINIO_ACCESS_KEY",
    "AUTH_SECRET",
    "SECRET_KEY",
    "TESTAGENT_SECRET_KEY",
    "IMAGE_PARSER_API_KEY",
]

# 跑 LLM 生成脚本/固定工具的子进程执行点文件（相对 backend/）。
# 新增加执行点时必须加入本清单——否则静态扫描覆盖不到。
EXECUTION_POINT_FILES = [
    "app/services/api_test_executor.py",
    "app/services/web_test_service.py",
    "app/services/storage_state_service.py",
    "app/agents/tools/web/execution_tools.py",
    "app/agents/tools/api/execution_tools.py",
    "app/agents/tools/android/execution_tools.py",
    "app/agents/tools/android/env_tools.py",
    "app/agents/tools/security/recon_tools.py",
    "app/agents/tools/security/exploit_tools.py",
    "app/utils/adb_utils.py",
    "app/utils/shell_env.py",
]

# 全量继承进程环境的危险写法（spawn env 场景）
FORBIDDEN_ENV_PATTERNS = [
    "os.environ.copy()",
    "{**os.environ}",
    "{** os.environ",
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def _sensitive_environ(monkeypatch):
    """向进程环境注入模拟敏感键。"""
    for key in SENSITIVE_KEYS:
        monkeypatch.setenv(key, f"secret-{key.lower()}")
    return monkeypatch


class TestRestrictedEnvCanary:
    """白名单内容金丝雀：敏感键零泄露。"""

    def test_no_sensitive_keys_leak(self, _sensitive_environ):
        env = build_script_exec_env()
        for key in SENSITIVE_KEYS:
            assert key not in env, f"敏感键 {key} 泄露进了脚本执行环境"

    def test_controlled_injection_channel_works(self, _sensitive_environ):
        env = build_script_exec_env({"AUTH_TOKEN": "biz-token", "CI": "1"})
        assert env["AUTH_TOKEN"] == "biz-token"
        assert env["CI"] == "1"

    def test_runtime_essentials_preserved(self, _sensitive_environ):
        env = build_restricted_env()
        assert env.get("PATH"), "PATH 必须保留（Node/npm 查找依赖）"
        if sys.platform == "win32":
            upper_keys = {k.upper() for k in env}
            assert "SYSTEMROOT" in upper_keys, "Windows CreateProcess 依赖 SYSTEMROOT"

    def test_build_script_exec_env_is_restricted(self, _sensitive_environ):
        """build_script_exec_env 必须基于白名单（防有人改回全继承）。"""
        env = build_script_exec_env()
        assert "DEEPSEEK_API_KEY" not in env


class TestExecutionPointsStaticGuard:
    """静态防回归：执行点文件禁止全量继承写法。"""

    @pytest.mark.parametrize("rel_path", EXECUTION_POINT_FILES)
    def test_no_full_env_inheritance(self, rel_path: str):
        path = BACKEND_ROOT / rel_path
        assert path.exists(), f"执行点文件不存在（可能已移动，需更新清单）: {rel_path}"
        content = path.read_text(encoding="utf-8")
        # shell_env.py 自身的文档字符串提及这些写法，豁免白名单构造函数文件
        if rel_path == "app/utils/shell_env.py":
            return
        for pattern in FORBIDDEN_ENV_PATTERNS:
            assert pattern not in content, (
                f"{rel_path} 出现全量继承写法 {pattern!r}——"
                f"子进程环境必须走 build_script_exec_env() 白名单"
            )


class TestProcWatchdog:
    """看门狗三路径（用 python 自身做被测子进程，无需 Node 环境）。"""

    def test_normal_completion_unaffected(self):
        result = run_cmd_with_watchdog(
            [sys.executable, "-c", "print('ok')"],
            timeout=30,
            max_memory_mb=2048,
            label="test-normal",
        )
        assert result.returncode == 0
        assert "ok" in (result.stdout or "")
        assert not getattr(result, "watchdog_killed", False)

    def test_memory_limit_kills_tree(self):
        result = run_cmd_with_watchdog(
            [
                sys.executable,
                "-c",
                "import time; x = bytearray(500*1024*1024); time.sleep(60)",
            ],
            timeout=120,
            max_memory_mb=100,
            label="test-oom",
        )
        assert getattr(result, "watchdog_killed", False)
        assert result.returncode != 0

    def test_timeout_raises(self):
        with pytest.raises(subprocess.TimeoutExpired):
            run_cmd_with_watchdog(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                timeout=2,
                max_memory_mb=2048,
                label="test-timeout",
            )
