import logging
import os

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v21.0/{phone_id}/messages"


def _get_url() -> str:
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    return _BASE_URL.format(phone_id=phone_id)


def _get_headers() -> dict:
    token = os.getenv("WHATSAPP_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ── Envio de texto simples (dentro da janela de 24 h) ───────────────

async def send_text(to: str, body: str) -> bool:
    """
    Envia mensagem de texto simples.
    Funciona apenas dentro da janela de 24 h do WhatsApp.
    Retorna True se enviou com sucesso.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    return await _post(payload, to, label="texto")


# ── Envio de Message Template (funciona fora da janela de 24 h) ─────

async def send_template(
    to: str,
    template_name: str,
    parameters: list[str],
    language: str = "pt_BR",
) -> bool:
    """
    Envia um Message Template aprovado pelo Meta.

    Args:
        to:             Telefone do destinatário (ex: '5511999999999')
        template_name:  Nome do template (ex: 'flight_tracking_start')
        parameters:     Lista ordenada de valores para {{1}}, {{2}}, etc.
        language:       Código do idioma do template (default: pt_BR)

    Retorna True se enviou com sucesso.
    """
    # Monta os componentes do body com parâmetros variáveis
    components = []
    if parameters:
        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(p)} for p in parameters
            ],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }

    return await _post(payload, to, label=f"template:{template_name}")


# ── Post genérico (interno) ─────────────────────────────────────────

async def _post(payload: dict, to: str, *, label: str) -> bool:
    """Envia o payload à Meta Cloud API. Retorna True se 2xx."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _get_url(), headers=_get_headers(), json=payload,
            )

        if resp.status_code >= 400:
            logger.error(
                "Falha ao enviar %s para %s: %s — %s",
                label, to, resp.status_code, resp.text,
            )
            return False

        logger.info("Enviado %s para %s", label, to)
        return True

    except httpx.HTTPError:
        logger.exception("Erro HTTP ao enviar %s para %s", label, to)
        return False
