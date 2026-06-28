#!/usr/bin/env python3
"""
Simple LangGraph API Server

A minimal script to start the LangGraph API server directly using uvicorn.
"""


import os
import sys
import json
from pathlib import Path

# 保证 stdout/stderr 使用 UTF-8，避免 Windows 默认 gbk 编码下打印 emoji 崩溃
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 在导入任何可能触发 deepagents 加载的模块之前，先确保 messages reducer 补丁已写入 .venv。
sys.path.insert(0, str(Path(__file__).parent))
from scripts.patch_deepagents import ensure_patched

if ensure_patched():
    print("已应用 deepagents messages reducer 补丁")

# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZG5WRU53PT06ZGM0NmYwNDk=

def setup_environment():
    """Setup required environment variables"""
    # Add src to Python path

    src_path = Path(__file__).parent / "backend"
    sys.path.insert(0, str(src_path))

    # Load graphs from langgraph.json
    config_path = Path(__file__).parent / "langgraph.json"
    graphs = {}
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZG5WRU53PT06ZGM0NmYwNDk=
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            graphs = config.get("graphs", {})
    
    # Set environment variables
    os.environ.update({
        # Database and storage - 使用自定义 PostgreSQL checkpointer
        # "POSTGRES_URI": "postgresql://postgres:postgres@localhost:5432/langgraph_checkpointer_db?sslmode=disable",
        # "REDIS_URI": "redis://localhost:6379",
        "DATABASE_URI": ":memory:",
        "REDIS_URI": "fake",
        # "MIGRATIONS_PATH": "/storage/migrations",
        "MIGRATIONS_PATH": "__inmem",
        # Server configuration
        "ALLOW_PRIVATE_NETWORK": "true",
        "LANGGRAPH_UI_BUNDLER": "true",
        "LANGGRAPH_RUNTIME_EDITION": "inmem",
        "LANGSMITH_LANGGRAPH_API_VARIANT": "local_dev",
        "LANGGRAPH_DISABLE_FILE_PERSISTENCE": "false",
        "LANGGRAPH_ALLOW_BLOCKING": "true",
        "LANGGRAPH_API_URL": "http://localhost:2025",

        # "LANGGRAPH_DEFAULT_RECURSION_LIMIT": "1000",
        
        # Graphs configuration
        "LANGSERVE_GRAPHS": json.dumps(graphs) if graphs else "{}",
        
        # Worker configuration
        "N_JOBS_PER_WORKER": "1",
    })
    
    # Load .env file if exists
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"✅ Loaded environment from .env")
        except ImportError:
            print("⚠️  python-dotenv not installed, skipping .env file")
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
        print(f"⚠️ Failed to apply monkey patch: {e}")
def main():
    """Start the server"""
    print("🚀 Starting Simple LangGraph API Server...")
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZG5WRU53PT06ZGM0NmYwNDk=
    
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
    # Print server information
    print("\n" + "="*60)
    print("📍 Server URL: http://localhost:2026")
    print("📚 API Documentation: http://localhost:2026/docs")
    print("🎨 Studio UI: http://localhost:2026/ui")
    print("💚 Health Check: http://localhost:2026/ok")
    print("="*60)
    
    try:
        # Import uvicorn after environment setup
        import uvicorn
        
        # Start the server directly
        uvicorn.run(
            "langgraph_api.server:app",
            host="0.0.0.0",
            port=2026,
            reload=False,
            access_log=False,
            log_config={
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
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZG5WRU53PT06ZGM0NmYwNDk=
