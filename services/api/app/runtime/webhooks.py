"""LiveKit webhook receiver (`application/webhook+json`, signed Authorization).

Server-only: LiveKit calls it, the browser never does. The body is read raw and
verified byte-for-byte; parsing it first and re-serializing would break the
SHA-256 the signed token carries.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.runtime.metrics import record_webhook
from app.service import postprocess, webhooks
from app.types import WebhookAck

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/webhooks/livekit",
    response_model=WebhookAck,
    responses={401: {"description": "Missing or invalid webhook signature"}},
)
async def livekit_webhook(request: Request, background: BackgroundTasks):
    raw = (await request.body()).decode("utf-8", errors="strict")
    authorization = request.headers.get("authorization", "")
    try:
        # Verification is CPU-only, but the evidence and manifest writes block
        # on boto3, so the whole receive runs in the threadpool.
        ack, to_process = await run_in_threadpool(webhooks.receive, raw, authorization)
    except webhooks.WebhookVerificationError as e:
        record_webhook(success=False)
        logger.warning("Rejected webhook: %s", e)
        raise HTTPException(status_code=401, detail="Invalid webhook signature") from None
    record_webhook(success=True)
    if to_process:
        background.add_task(postprocess.process_session, to_process)
    return ack
