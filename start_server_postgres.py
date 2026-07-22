#!/usr/bin/env python3
"""
Simple LangGraph API Server

A minimal script to start the LangGraph API server directly using uvicorn.
modified according to cli.py under LangGraph API
"""


import os
import sys
import json
import asyncio
from pathlib import Path

# 保证 stdout/stderr 使用 UTF-8，避免 Windows 默认 gbk 编码下打印 emoji 崩溃
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 在导入任何可能触发 deepagents 加载的模块之前，先确保 messages reducer 补丁已写入 .venv。
# deepagents/__init__.py 会急切导入 deepagents.graph 并按值绑定 reducer，运行时 monkey-patch
# 来不及生效，因此只能直接修改已安装源文件。
sys.path.insert(0, str(Path(__file__).parent))
from scripts.patch_deepagents import ensure_patched

if ensure_patched():
    print("已应用 deepagents messages reducer 补丁")

# Windows 上 psycopg 异步模式不兼容默认的 ProactorEventLoop，必须切到 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def setup_environment():
    """Setup required environment variables"""
    # Add src and backend to Python path so graph modules can import app.*
    backend_path = Path(__file__).parent / "backend"
    sys.path.insert(0, str(backend_path))

    # 先加载 .env，让后续逻辑能读到里面的 POSTGRES_URI / REDIS_URI 等
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"✅ Loaded environment from .env")
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env file")

    # Load config from langgraph.json
    config_path = Path(__file__).parent / "langgraph.json"
    graphs = {}
    auth = None

    root_dir = Path(__file__).parent.resolve()
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJkYWJ3PT06N2E5YWVjMTk=

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            graphs = config.get("graphs", {})
            auth = config.get("auth")  # 读取 auth 配置

        # 将 langgraph.json 中的相对路径转换为绝对路径，避免 cwd 影响 graph 加载
        # LangGraph 只认 '/' 作为文件路径分隔符，所以必须把 Windows 反斜杠换成正斜杠
        for key, spec in list(graphs.items()):
            if isinstance(spec, dict) and "path" in spec:
                p = Path(spec["path"])
                if not p.is_absolute():
                    spec["path"] = str(root_dir / p).replace("\\", "/")
            elif isinstance(spec, str):
                p = Path(spec)
                if not p.is_absolute():
                    graphs[key] = {"path": str(root_dir / p).replace("\\", "/")}

    # 从环境变量（来自 .env）读取数据库 / Redis 连接信息
    # 兼容两种命名：POSTGRES_URI / DATABASE_URI
    postgres_uri = os.environ.get("POSTGRES_URI") or os.environ.get("DATABASE_URI")
    redis_uri = os.environ.get("REDIS_URI")
    migrations_path = os.environ.get("MIGRATIONS_PATH", "./storage/migrations")

    missing = []
    if not postgres_uri:
        missing.append("POSTGRES_URI (或 DATABASE_URI)")
    if not redis_uri:
        missing.append("REDIS_URI")
    if missing:
        print(f"❌ 缺少必要的环境变量，请在 .env 中配置: {', '.join(missing)}")
        sys.exit(1)

    # 复用 .env 里的 CORS_ORIGINS，避免 LangGraph Server 使用默认 "*" 时
    # 与 allow_credentials=True 冲突导致浏览器报 CORS 错误。
    # 注意：浏览器把 localhost 和 127.0.0.1 视为不同 origin，都要列出。
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000",
                     "http://localhost:3001", "http://localhost:8080"]
    if raw_cors := os.environ.get("CORS_ORIGINS"):
        try:
            _cors_origins = json.loads(raw_cors)
            if not isinstance(_cors_origins, list):
                _cors_origins = list(_cors_origins)
        except json.JSONDecodeError:
            print(f"⚠️  CORS_ORIGINS 解析失败，使用默认列表: {raw_cors}")

    # Build environment variables dict
    env_vars = {
        # Database and storage - 从 .env 读取
        "POSTGRES_URI": postgres_uri,
        "REDIS_URI": redis_uri,
        "MIGRATIONS_PATH": migrations_path,
        # 本地 in-memory 无数据库持久化时
        #"DATABASE_URI": ":memory:",
        #"REDIS_URI": "fake",
        #"MIGRATIONS_PATH": "__inmem",

        # Server configuration
        "ALLOW_PRIVATE_NETWORK": "true",
        "LANGGRAPH_UI_BUNDLER": "true",
        "LANGGRAPH_RUNTIME_EDITION": "postgres",
        "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
        "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "false",
        "LANGGRAPH_ALLOW_BLOCKING": "true",
        "LANGGRAPH_API_URL": "http://localhost:2026",
        "CORS_ALLOW_ORIGINS": json.dumps(_cors_origins),

        "LANGGRAPH_DEFAULT_RECURSION_LIMIT": "2000",

        # Graphs configuration
        "LANGSERVE_GRAPHS": json.dumps(graphs) if graphs else "{}",

        # Auth configuration - 从 langgraph.json 读取
        "LANGGRAPH_AUTH": json.dumps(auth) if auth else None,

        # Worker configuration
        "N_JOBS_PER_WORKER": "5",
        "BG_JOB_ISOLATED_LOOPS": "true",
    }

    # 过滤掉 None 值，然后设置环境变量
    os.environ.update({k: v for k, v in env_vars.items() if v is not None})
def monkey_patch():
    # Harden deepagents' messages DeltaChannel against corrupt pending writes.
    #
    # Symptom: GET /threads/{id}/history (and /state) returns HTTP 400 with
    #   "Message dict must contain 'role' and 'content' keys, got {'value': [...]}"
    # which the browser surfaces as a misleading CORS/fetch error (the 400 body
    # carries no CORS headers). The {'value': [...]} payload is an interrupt /
    # snapshot blob that leaked into the messages channel's pending writes; when
    # langgraph replays those writes through deepagents' _messages_delta_reducer
    # during checkpoint reconstruction, convert_to_messages() chokes on it.
    #
    # Why the previous patch did nothing: it rebound
    #   deepagents._messages_reducer._messages_delta_reducer = patched_reducer
    # but `import deepagents._messages_reducer` first runs deepagents/__init__,
    # which imports deepagents.graph, which builds the messages DeltaChannel with
    # a *direct reference* to the original reducer. Rebinding the module attribute
    # afterwards never reaches that already-captured reference, so the channel
    # kept calling the un-sanitized reducer.
    #
    # Fix: wrap the reducer the channel actually holds — both for every future
    # channel reconstruction (DeltaChannel.__init__, used by copy()/from_checkpoint
    # during state/history replay) and for the channel instances already built on
    # deepagents' state classes.
    try:
        import inspect
        import typing
        import deepagents.graph as _graph_mod
        from langchain_core.messages import BaseMessage, convert_to_messages
        from langgraph.channels.delta import DeltaChannel

        _WRAPPED = "_dt_sanitized"

        def _is_message_like(item) -> bool:
            if isinstance(item, BaseMessage):
                return True
            try:
                convert_to_messages([item])
                return True
            except Exception:
                return False

        def _unwrap(obj):
            # Leaked interrupt / _DeltaSnapshot payloads look like {'value': [...]}.
            while isinstance(obj, dict) and set(obj) == {"value"}:
                obj = obj["value"]
            return obj

        def _clean_seq(seq):
            seq = _unwrap(seq)
            if not isinstance(seq, list):
                return seq if _is_message_like(seq) else []
            out = []
            for it in seq:
                it = _unwrap(it)
                if isinstance(it, list):
                    out.extend(x for x in it if _is_message_like(x))
                elif _is_message_like(it):
                    out.append(it)
            return out

        def _wrap_reducer(reducer):
            if getattr(reducer, _WRAPPED, False):
                return reducer

            def sanitizing(state, writes):
                state = [] if state is None else _clean_seq(state)
                clean_writes = []
                for w in writes:
                    if isinstance(w, list):
                        clean_writes.append(_clean_seq(w))
                        continue
                    w = _unwrap(w)
                    if isinstance(w, list):
                        clean_writes.append(_clean_seq(w))
                    elif _is_message_like(w):
                        clean_writes.append(w)
                    # else: drop the malformed single write
                return reducer(state, clean_writes)

            setattr(sanitizing, _WRAPPED, True)
            return sanitizing

        # (1) Every channel reconstruction (copy / from_checkpoint) builds via
        #     __init__, so wrapping it covers the state/history replay path.
        _orig_init = DeltaChannel.__init__
        if not getattr(_orig_init, _WRAPPED, False):
            def patched_init(self, reducer, *args, **kwargs):
                _orig_init(self, _wrap_reducer(reducer), *args, **kwargs)
            setattr(patched_init, _WRAPPED, True)
            DeltaChannel.__init__ = patched_init

        # (2) Re-wrap the channels already built on deepagents' state classes.
        def _collect(tp, acc):
            for meta in getattr(tp, "__metadata__", ()) or ():
                if isinstance(meta, DeltaChannel):
                    acc.append(meta)
            for arg in getattr(tp, "__args__", ()) or ():
                _collect(arg, acc)

        rewrapped = 0
        for _, cls in inspect.getmembers(_graph_mod, inspect.isclass):
            try:
                hints = typing.get_type_hints(cls, include_extras=True)
            except Exception:
                continue
            for tp in hints.values():
                acc = []
                _collect(tp, acc)
                for ch in acc:
                    ch.reducer = _wrap_reducer(ch.reducer)
                    rewrapped += 1

        print(f"🩹 Hardened deepagents message reducer (channels rewrapped: {rewrapped})")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ Failed to apply monkey patch: {e}")

def main():
    """Start the server"""
    print("🚀 Starting Simple LangGraph API Server...")

    # Setup environment
    setup_environment()
    # NOTE: 不再调用 monkey_patch()。它对 DeltaChannel.__init__ 做全局包装，
    # 会给重建出来的 channel 套一个名为 `sanitizing` 的闭包 reducer，而模块级
    # 原始 channel（如 filesystem 的 `files`）仍持有原函数。langgraph 的
    # DeltaChannel.__eq__ 用 `reducer is reducer` 做身份判等，两者不再相等，
    # StateGraph._add_schema 合并 schema 时即抛
    # "Channel 'files' already exists with a different type"，导致 api_agent 加载失败。
    # messages 的 {'value':[...]} 清洗已直接落在源 reducer
    # .venv/.../deepagents/_messages_reducer.py 中，无需此补丁。
    # monkey_patch()
    # 调试输出：确认 graph 配置已正确写入环境变量
    print(f"📋 LANGSERVE_GRAPHS = {os.environ.get('LANGSERVE_GRAPHS', 'NOT SET')}")
    print(f"📋 LANGGRAPH_RUNTIME_EDITION = {os.environ.get('LANGGRAPH_RUNTIME_EDITION', 'NOT SET')}")

    # Print server information
    print("\n" + "="*60)
    print("📍 Server URL: http://localhost:2026")
    print("📚 API Documentation: http://localhost:2026/docs")
    print("🎨 Studio UI: http://localhost:2026/ui")
    print("💚 Health Check: http://localhost:2026/ok")
    print("="*60)

    try:
        import uvicorn

        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
            "loggers": {
                "uvicorn": {"level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"level": "WARNING"},
            }
        }

        config = uvicorn.Config(
            "langgraph_api.server:app",
            host="0.0.0.0",
            port=2026,
            reload=False,
            access_log=False,
            loop="asyncio",
            log_config=log_config,
        )
        server = uvicorn.Server(config)

        # Windows 上 psycopg 异步模式不兼容默认的 ProactorEventLoop，
        # 必须用 loop_factory 显式创建 SelectorEventLoop
        if sys.platform == "win32":
            import selectors

            def _selector_loop_factory():
                return asyncio.SelectorEventLoop(selectors.SelectSelector())
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YjJkYWJ3PT06N2E5YWVjMTk=

            asyncio.run(server.serve(), loop_factory=_selector_loop_factory)
        else:
            asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
