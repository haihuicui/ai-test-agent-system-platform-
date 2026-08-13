"""LightRAG workspace 路由验证实例（本地轻量存储，独立 working_dir）。

远程中间件（Milvus/Neo4j）未启动时，用本地存储实现验证
per-request workspace 路由逻辑（注册表 + 代理 + middleware）。
存储经 env 变量覆盖（LIGHTRAG_*_STORAGE），LLM/Embedding binding
由 .env 自动加载。
"""
import os
import sys

os.environ["LIGHTRAG_KV_STORAGE"] = "JsonKVStorage"
os.environ["LIGHTRAG_DOC_STATUS_STORAGE"] = "JsonDocStatusStorage"
os.environ["LIGHTRAG_GRAPH_STORAGE"] = "NetworkXStorage"
os.environ["LIGHTRAG_VECTOR_STORAGE"] = "NanoVectorDBStorage"

sys.argv = [
    "lightrag-server",
    "--host", "127.0.0.1",
    "--port", "9622",
    "--working-dir", "./verify_ws_data",
    "--input-dir", "./verify_ws_inputs",
]

from lightrag.api.lightrag_server import main

main()
