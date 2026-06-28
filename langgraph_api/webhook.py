
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
# noqa  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VmpORVFnPT06NDg2ZDc0Y2E=

from langgraph_api.config import HTTP_CONFIG
from langgraph_api.http import get_http_client, get_loopback_client, http_request

if TYPE_CHECKING:
    from langgraph_api.worker import WorkerResult
# type: ignore  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VmpORVFnPT06NDg2ZDc0Y2E=

logger = structlog.stdlib.get_logger(__name__)

# pragma: no cover  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VmpORVFnPT06NDg2ZDc0Y2E=

async def call_webhook(result: "WorkerResult") -> None:
    if HTTP_CONFIG and HTTP_CONFIG.get("disable_webhooks"):
        logger.info(
            "Webhooks disabled, skipping webhook call", webhook=result["webhook"]
        )
        return

    checkpoint = result["checkpoint"]
    payload = {
        **result["run"],
        "status": result["status"],
        "run_started_at": result["run_started_at"],
        "run_ended_at": result["run_ended_at"],
        "webhook_sent_at": datetime.now(UTC).isoformat(),
        "values": checkpoint["values"] if checkpoint else None,
    }
    if exception := result["exception"]:
        payload["error"] = str(exception)
    webhook = result.get("webhook")
    if webhook:
        try:
            if webhook.startswith("/"):
                # Call into this own app
                webhook_client = get_loopback_client()
            else:
                webhook_client = get_http_client()
            await http_request("POST", webhook, json=payload, client=webhook_client)
            await logger.ainfo(
                "Background worker called webhook",
                webhook=result["webhook"],
                run_id=result["run"]["run_id"],
            )
        except Exception as exc:
            logger.exception(
                f"Background worker failed to call webhook {result['webhook']}",
                exc_info=exc,
                webhook=result["webhook"],
            )
