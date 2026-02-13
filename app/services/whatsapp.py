import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = (
    "https://graph.facebook.com/v21.0/{phone_id}/messages"
)


async def send_message(to: str, body: str) -> None:
    """Envia uma mensagem de texto simples via Meta Cloud API."""
    url = WHATSAPP_API_URL.format(phone_id=settings.whatsapp_phone_number_id)
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        logger.error("Falha ao enviar mensagem WhatsApp: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    logger.info("Mensagem enviada para %s", to)
