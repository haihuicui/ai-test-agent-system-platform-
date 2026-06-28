"""
Playwright 异步运行器

使用 asyncio.create_subprocess_exec 执行 Playwright 测试，
避免阻塞事件循环。
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.execution.models import RunnerResult

logger = logging.getLogger(__name__)

# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtWUlZBPT06YzRhZmRjNzY=

def _get_npx_cmd() -> list[str]:
    """
    获取平台相关的 npx 命令。

    Windows 上 asyncio.create_subprocess_exec 不经过 shell，
    需要显式使用 npx.cmd 或在 PATH 中能找到 .cmd 文件。
    """
    if os.name == "nt":  # Windows
        return ["npx.cmd"]
    return ["npx"]


def _ensure_node_in_path(env: dict[str, str]) -> dict[str, str]:
    """确保 PATH 包含常见的 Node.js 安装目录。"""
    node_paths = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\npm"),
        "/usr/local/bin",
        "/usr/bin",
    ]
    current_path = env.get("PATH", "")
    # 只添加当前 PATH 中不存在的路径
    paths_to_add = [p for p in node_paths if p not in current_path]
    if paths_to_add:
        env = {**env, "PATH": os.pathsep.join(paths_to_add + [current_path])}
    return env


class PlaywrightRunner:
    """Playwright 测试异步运行器"""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir.resolve()
        self.tests_dir = self.workspace_dir / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        script_path: Path,
        config: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ) -> RunnerResult:
        """
        异步执行单个 Playwright 测试脚本。

        Args:
            script_path: 测试脚本路径（相对于 workspace_dir 或绝对路径）
            config: 执行配置 {base_url, reporter, env, ...}
            timeout: 超时时间（秒）

        Returns:
            RunnerResult
        """
        start_time = datetime.now(timezone.utc)
        config = config or {}
        proc: Optional[asyncio.subprocess.Process] = None
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtWUlZBPT06YzRhZmRjNzY=

        # 环境变量：确保 PATH 包含 Node.js
        env = _ensure_node_in_path({**os.environ})
        if config.get("base_url"):
            env["API_BASE_URL"] = config["base_url"]
        if config.get("reporter", "list") == "html":
            env["CI"] = "1"
        env_vars = config.get("env") or config.get("environment_variables")
        if env_vars:
            env.update(env_vars)

        npx_cmd = _get_npx_cmd()

        # 1. 验证 npx 可用
        try:
            npx_proc = await asyncio.create_subprocess_exec(
                *npx_cmd, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(npx_proc.communicate(), timeout=10)
            if npx_proc.returncode != 0:
                return RunnerResult(
                    success=False,
                    error_message=f"npx 不可用: {stderr.decode('utf-8', errors='replace')}",
                )
        except asyncio.TimeoutError:
            return RunnerResult(success=False, error_message="npx 检查超时")
        except Exception as e:
            return RunnerResult(success=False, error_message=f"npx 检查失败: {e}")

        # 2. 解析脚本路径
        if not script_path.is_absolute():
            script_path = self.workspace_dir / script_path

        if not script_path.exists():
            return RunnerResult(
                success=False,
                error_message=f"脚本文件不存在: {script_path}",
            )

        relative_path = script_path.relative_to(self.workspace_dir)

        # 3. 构建命令
        reporter = config.get("reporter", "list")
        cmd = [
            *npx_cmd, "playwright", "test",
            relative_path.as_posix(),
            f"--reporter={reporter}",
        ]

        logger.info(
            "[PlaywrightRunner] 执行命令: %s, 工作目录: %s",
            " ".join(cmd),
            self.workspace_dir,
        )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtWUlZBPT06YzRhZmRjNzY=

        # 4. 启动异步子进程
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            return RunnerResult(
                success=False,
                error_message=f"启动子进程失败: {e}",
                duration_ms=duration_ms,
            )

        # 5. 等待执行完成（带超时）
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("[PlaywrightRunner] 执行超时，正在终止子进程...")
            if proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    pass
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            return RunnerResult(
                success=False,
                error_message=f"测试执行超时（超过 {timeout} 秒）",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            return RunnerResult(
                success=False,
                error_message=f"等待子进程完成时出错: {e}",
                duration_ms=duration_ms,
            )

        # 6. 解析输出
        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # 检查报告（支持 "list,html" 等多 reporter 组合）
        report_path = None
        if "html" in reporter:
            report_dir = self.workspace_dir / "playwright-report"
            if (report_dir / "index.html").exists():
                report_path = str(report_dir)

        # 尝试从 stdout 解析测试统计
        result_summary = self._parse_summary(stdout)

        success = proc.returncode == 0
        error_message = None if success else (stderr[:2000] or stdout[:2000])

        logger.info(
            "[PlaywrightRunner] 执行完成, returncode=%s, duration_ms=%s, "
            "passed=%s, failed=%s",
            proc.returncode,
            duration_ms,
            result_summary.get("passed", 0),
            result_summary.get("failed", 0),
        )

        return RunnerResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            returncode=proc.returncode,
            report_path=report_path,
            duration_ms=duration_ms,
            error_message=error_message,
            result_summary=result_summary,
        )

    def _parse_summary(self, stdout: str) -> Dict[str, int]:
        """从 Playwright list reporter 输出解析测试统计。"""
        result = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

        # 匹配形如 "6 passed (2.5s)" 或 "2 failed, 4 passed"
        summary_match = re.search(
            r"(\d+)\s+passed",
            stdout,
        )
        if summary_match:
            result["passed"] = int(summary_match.group(1))
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtWUlZBPT06YzRhZmRjNzY=

        failed_match = re.search(r"(\d+)\s+failed", stdout)
        if failed_match:
            result["failed"] = int(failed_match.group(1))

        skipped_match = re.search(r"(\d+)\s+skipped", stdout)
        if skipped_match:
            result["skipped"] = int(skipped_match.group(1))

        total_match = re.search(r"Total:\s+(\d+)\s+test", stdout)
        if total_match:
            result["total"] = int(total_match.group(1))
        else:
            result["total"] = result["passed"] + result["failed"] + result["skipped"]

        return result
