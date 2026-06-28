
import argparse
import asyncio
import json
import logging.config
import pathlib

from langgraph_api.queue_entrypoint import main as queue_main


async def main(grpc_port: int = 50051):
    with open(pathlib.Path(__file__).parent.parent / "logging.json", encoding="utf-8") as file:
        loaded_config = json.load(file)
        logging.config.dictConfig(loaded_config)
    try:
        import uvloop  # type: ignore[unresolved-import]
# noqa  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TjFsR2N3PT06Y2M4MmM5MGQ=

        uvloop.install()
    except ImportError:
        pass
    from langgraph_api import config

    config.IS_EXECUTOR_ENTRYPOINT = True
    await queue_main(grpc_port=grpc_port, entrypoint_name="python-executor")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--grpc-port", type=int, default=50051)
    args = parser.parse_args()
    asyncio.run(main(grpc_port=args.grpc_port))
# type: ignore  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TjFsR2N3PT06Y2M4MmM5MGQ=
