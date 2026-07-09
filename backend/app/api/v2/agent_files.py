"""
Agent 工作区文件下载 API

允许前端下载 Agent 在虚拟文件系统中生成的文件（如 Excel 导出文件）。
路径严格限制在 testcase workspace_root 内，防止目录遍历。
"""

from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config.settings import settings


router = APIRouter(prefix="/agents/files", tags=["Agent 文件"])


def _resolve_virtual_path(virtual_path: str) -> Path:
    """把虚拟路径解析为 workspace 中的真实路径，并校验不越界。"""
    workspace_root = Path(settings.testcase_workspace_root).resolve()

    # 去掉前导 / 并 URL 解码
    clean_path = unquote(virtual_path).lstrip("/")
    if not clean_path:
        raise HTTPException(status_code=400, detail="文件路径不能为空")

    # 解析绝对路径
    target = (workspace_root / clean_path).resolve()

    # 防止目录遍历：目标路径必须在 workspace_root 之内
    try:
        target.relative_to(workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问工作区之外的文件") from exc

    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="路径不是文件")

    return target


@router.get("/download")
async def download_agent_file(
    path: str = Query(..., description="Agent 虚拟文件路径，如 /测试用例.xlsx"),
):
    """下载 Agent 工作区中的文件。"""
    target = _resolve_virtual_path(path)
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/octet-stream",
    )
