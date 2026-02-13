import logging

from fastapi import APIRouter, Query, Request, Response

from app.config import settings
from app.models.schemas import FlightRecord, WhatsAppWebhookPayload
from app.services.aviationstack import get_flight_info
from app.services.database import save_flight
from app.services.nlp import extract_flight_code
from app.services.whatsapp import send_message

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Verificação do webhook (GET) ─────────────────────────────────────
@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    """Meta envia um GET para verificar o endpoint do webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("Webhook verificado com sucesso")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("Falha na verificação do webhook")
    return Response(content="Forbidden", status_code=403)


# ── Recebimento de mensagens (POST) ──────────────────────────────────
@router.post("/webhook")
async def receive_message(request: Request) -> dict:
    """Recebe mensagens do WhatsApp, extrai voo, consulta API e responde."""
    body = await request.json()
    payload = WhatsAppWebhookPayload(**body)

    for entry in payload.entry:
        for change in entry.changes:
            messages = change.value.messages
            if not messages:
                continue

            for msg in messages:
                if msg.type != "text" or msg.text is None:
                    continue

                user_phone = msg.from_
                user_text = msg.text.body
                logger.info("Mensagem de %s: %s", user_phone, user_text)

                await _handle_text_message(user_phone, user_text)

    return {"status": "ok"}


async def _handle_text_message(user_phone: str, text: str) -> None:
    """Pipeline: extrair voo -> consultar API -> salvar -> responder."""

    # 1. Extrair código do voo
    flight_code = await extract_flight_code(text)
    if not flight_code:
        await send_message(
            user_phone,
            "Não consegui identificar um número de voo na sua mensagem. "
            "Por favor, envie o código do voo (ex: LA3456, G31234).",
        )
        return

    # 2. Consultar AviationStack
    try:
        flight = await get_flight_info(flight_code)
    except Exception:
        logger.exception("Erro ao consultar AviationStack para %s", flight_code)
        await send_message(
            user_phone,
            f"Ocorreu um erro ao buscar informações do voo {flight_code}. "
            "Tente novamente em alguns instantes.",
        )
        return

    if not flight:
        await send_message(
            user_phone,
            f"Não encontrei dados para o voo {flight_code}. "
            "Verifique o código e tente novamente.",
        )
        return

    # 3. Salvar no Supabase
    try:
        record = FlightRecord(
            user_phone=user_phone,
            flight_iata=flight_code,
            flight_status=flight.flight_status,
            departure_airport=flight.departure.airport,
            arrival_airport=flight.arrival.airport,
            scheduled_departure=flight.departure.scheduled,
            scheduled_arrival=flight.arrival.scheduled,
        )
        save_flight(record)
    except Exception:
        logger.exception("Erro ao salvar voo no banco")

    # 4. Montar e enviar resposta
    status_emoji = {
        "scheduled": "📅 Programado",
        "active": "✈️ Em voo",
        "landed": "✅ Pousou",
        "cancelled": "❌ Cancelado",
        "incident": "⚠️ Incidente",
        "diverted": "↩️ Desviado",
    }
    status_text = status_emoji.get(
        flight.flight_status or "", flight.flight_status or "Desconhecido"
    )

    dep = flight.departure
    arr = flight.arrival
    delay_info = ""
    if dep.delay and dep.delay > 0:
        delay_info = f"\n⏱ Atraso na partida: {dep.delay} min"

    reply = (
        f"*Voo {flight_code}* — {flight.airline.name or 'N/A'}\n"
        f"Status: {status_text}\n\n"
        f"🛫 *Partida*: {dep.airport or 'N/A'} ({dep.iata or ''})\n"
        f"   Previsto: {dep.scheduled or 'N/A'}\n"
        f"🛬 *Chegada*: {arr.airport or 'N/A'} ({arr.iata or ''})\n"
        f"   Previsto: {arr.scheduled or 'N/A'}"
        f"{delay_info}\n\n"
        f"Voo salvo! Você receberá atualizações."
    )
    await send_message(user_phone, reply)
