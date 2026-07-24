"""Windows 下启动 langgraph dev 的包装脚本。

修复两个问题：
1. Windows 默认 asyncio SelectorEventLoop 不支持 subprocess，需要切换为
   ProactorEventLoopPolicy（必须在事件循环创建前设置）。
2. .env 文件含中文，默认 GBK 解码会失败，强制 UTF-8 模式。

用法（替换原来的 `langgraph dev --port 2026`）：
    python scripts/run_langgraph_dev.py --port 2026
"""

import asyncio
import os
import sys

# 必须在任何事件循环创建前执行
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 强制 Python 以 UTF-8 打开文本文件，避免 dotenv 解析中文 .env 时 GBK 报错
os.environ.setdefault("PYTHONUTF8", "1")

# 确保 backend 在 Python 路径中，使 langgraph 能导入 app.* 模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# 将工作目录切换到项目根目录，让 langgraph.json 被正确加载
os.chdir(project_root)

# 调用 langgraph CLI 入口
from langgraph_cli.cli import cli

if __name__ == "__main__":
    sys.argv.insert(1, "dev")
    # Windows 下 langgraph dev 的 watchfiles 热重载会替换为 SelectorEventLoop，
    # 导致无法启动 MCP stdio subprocess；关闭热重载并使用 ProactorEventLoop。
    if sys.platform == "win32":
        if "--no-reload" not in sys.argv:
            sys.argv.append("--no-reload")
        if "--allow-blocking" not in sys.argv:
            sys.argv.append("--allow-blocking")
    cli()
