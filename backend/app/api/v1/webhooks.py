from __future__ import annotations

import logging

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)


@router.post("/{integration_name}")
async def receive_webhook(integration_name: str, request: Request) -> dict:
    """Generic webhook endpoint for future integrations."""
    body = await request.body()
    logger.info("Webhook received for integration '%s': %d bytes", integration_name, len(body))
    return {"status": "ok"}
