"""会话级 workspace 路径规范化。

所有落在 testcase workspace 的会话产物（功能矩阵、用例 JSONL、manifest、
导出文件）统一隔离到 ``workspace_root/<project>/<thread_id>/`` 下，
保证同项目并发会话互不覆盖文件。

对模型透明：纯文件名自动补会话前缀；带项目前缀的路径插入会话层；
已含完整会话前缀的路径原样保留（幂等，兼容 read_path 回传）。
拿不到会话作用域时（非平台环境 / 单元测试直调工具）回退到旧的
项目级隔离行为。
"""

import re
from pathlib import Path

from app.agents.tools.testcase.runtime_context import (
    get_session_project,
    get_session_thread_id,
)


def sanitize_path_segment(value: str, field: str = "路径段") -> str:
    """将任意标识符清洗为安全的单级目录名。

    与 feature_matrix_tools._sanitize_project_identifier 同一套规则：
    替换路径分隔符与文件系统非法字符，拒绝 '.'/'..' 等歧义值。
    """
    cleaned = value.strip()
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", cleaned)
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"无效的{field}：{value!r}")
    return cleaned


def session_scope_segments(project_identifier: str = "") -> tuple[str, str]:
    """解析当前生效的会话隔离前缀段（project, thread）。

    project 显式传参优先，否则读 contextvar；thread 只从 contextvar 取
    （thread_id 是平台注入的运行时标识，模型不可指定）。
    任一侧缺失时对应段为 ""（调用方据此回退旧行为）。
    """
    raw_project = project_identifier.strip() or (get_session_project() or "")
    project = ""
    if raw_project:
        try:
            project = sanitize_path_segment(raw_project, "项目标识符")
        except ValueError:
            project = ""

    raw_thread = (get_session_thread_id() or "").strip()
    thread = ""
    if raw_thread:
        try:
            thread = sanitize_path_segment(raw_thread, "会话标识")
        except ValueError:
            thread = ""

    return project, thread


def apply_session_scope(rel: Path, project_identifier: str = "") -> Path:
    """在 workspace 相对路径上应用会话隔离前缀（幂等）。

    规则（project / thread 均有效时）：
      - ``rel`` 已以 ``<project>/<thread>/`` 开头 → 原样返回；
      - ``rel`` 以 ``<project>/`` 开头 → 插入 thread 层；
      - 其他（纯文件名、自定义子目录）→ 补全 ``<project>/<thread>/`` 前缀。
    thread 缺失时退化为项目级前缀（旧行为）；project 也缺失时原样返回。
    """
    project, thread = session_scope_segments(project_identifier)
    if not project:
        return rel

    parts = rel.parts
    if not parts:
        return rel

    if parts[0] == project:
        if thread:
            if len(parts) >= 2 and parts[1] == thread:
                return rel  # 已含完整会话前缀（如 read_path 回传）
            return Path(project, thread, *parts[1:])
        return rel  # 无 thread：项目级前缀已存在

    if thread:
        return Path(project, thread, *parts)
    return Path(project, *parts)
