"""自动把受控的 deepagents messages reducer 补丁写入当前虚拟环境。

该补丁无法通过 monkey-patch 在运行时生效，因为 deepagents/__init__.py
会急切导入 deepagents.graph，后者在类定义时就把 reducer 按值绑定进
DeltaChannel。因此必须在 deepagents 首次被导入前，直接修改已安装包源文件。

用法：
    from scripts.patch_deepagents import ensure_patched
    ensure_patched()  # 必须在 import deepagents 之前调用

也可以命令行手动执行：
    python scripts/patch_deepagents.py
"""
from __future__ import annotations

import shutil
import sys
import sysconfig
from pathlib import Path

PATCH_MARKER = "PATCH: messages_reducer_sanitized_v1"


def _venv_site_packages() -> Path:
    """定位当前解释器对应的 site-packages 目录（跨平台）。

    Windows venv 布局是 .venv/Lib/site-packages，Linux/macOS 是
    .venv/lib/pythonX.Y/site-packages。sysconfig 跟随 sys.executable，
    两种布局都能正确解析，避免硬编码导致 Linux 容器启动即 FileNotFoundError。
    """
    return Path(sysconfig.get_paths()["purelib"])


def _target_file() -> Path:
    return _venv_site_packages() / "deepagents" / "_messages_reducer.py"


def _patch_source_file() -> Path:
    """定位仓库里受控的补丁源文件。"""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent / "patches" / "deepagents" / "_messages_reducer.py"


def ensure_patched() -> bool:
    """如果 deepagents/_messages_reducer.py 尚未补丁，则写入补丁。

    Returns:
        True 表示本次执行写入了补丁；False 表示已是最新状态无需改动。
    """
    target = _target_file()
    source = _patch_source_file()

    if not target.exists():
        raise FileNotFoundError(
            f"deepagents 未安装或路径异常，找不到目标文件: {target}"
        )
    if not source.exists():
        raise FileNotFoundError(
            f"补丁源文件缺失: {source}，请确认 patches/deepagents/_messages_reducer.py 存在"
        )

    current_text = target.read_text(encoding="utf-8")
    if PATCH_MARKER in current_text:
        return False

    backup = target.with_suffix(target.suffix + ".orig")
    if not backup.exists():
        shutil.copy2(target, backup)

    source_text = source.read_text(encoding="utf-8")
    target.write_text(source_text, encoding="utf-8")
    return True


if __name__ == "__main__":
    try:
        applied = ensure_patched()
        print(
            f"{'已应用' if applied else '已是最新'} deepagents messages reducer 补丁"
        )
        sys.exit(0)
    except Exception as e:
        print(f"应用补丁失败: {e}", file=sys.stderr)
        sys.exit(1)
