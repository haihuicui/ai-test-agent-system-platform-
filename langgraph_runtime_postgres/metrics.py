
from langgraph_api import config
from typing_extensions import TypedDict
# pragma: no cover  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2V1VGQ05RPT06ZDRiMTY0YjA=

from langgraph_runtime_postgres import queue


class WorkerMetrics(TypedDict):
    max: int
    active: int
    available: int

# fmt: off  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2V1VGQ05RPT06ZDRiMTY0YjA=

class Metrics(TypedDict):
    workers: WorkerMetrics


def get_metrics() -> Metrics:
    workers_max = config.N_JOBS_PER_WORKER
    workers_active = queue.get_num_workers()
    return Metrics(
        workers=WorkerMetrics(
            max=workers_max,
            active=workers_active,
            available=workers_max - workers_active,
        )
    )
