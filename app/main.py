import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response

load_dotenv()

from app.database import add_subscription
from app.services import (
    check_flight_existence,
    extract_flight_info,
    send_whatsapp_text,
)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Flight Tracker", version="0.2.0")


# ── GET /webhook — Verificação do Facebook ───────────────────────────
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """
    O Facebook envia um GET com três query params para validar o endpoint.
    Se hub.mode == 'subscribe' e o token bater, devolvemos hub.challenge.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso!")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Falha na verificação do webhook (token inválido)")
    return Response(content="Forbidden", status_code=403)


# ── POST /webhook — Pipeline completo ───────────────────────────────
@app.post("/webhook")
async def receive_message(request: Request):
    """
    Pipeline reativo completo:
    1. Recebe mensagem do WhatsApp
    2. IA extrai flight_iata + date
    3. Valida na AviationStack
    4. Salva no Supabase
    5. Responde ao usuário via WhatsApp
    """
    body = await request.json()
    logger.info("Payload recebido:\n%s", json.dumps(body, indent=2, ensure_ascii=False))

    # ── Extrair mensagem de texto do payload do WhatsApp ─────────
    messages = _extract_messages(body)
    for user_phone, user_text in messages:
        await _handle_message(user_phone, user_text)

    return {"status": "ok"}


def _extract_messages(body: dict) -> list[tuple[str, str]]:
    """Extrai pares (telefone, texto) do payload do WhatsApp."""
    results = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") == "text" and msg.get("text", {}).get("body"):
                    results.append((msg["from"], msg["text"]["body"]))
    return results


async def _handle_message(user_phone: str, user_text: str) -> None:
    """Orquestra todo o fluxo reativo para uma mensagem recebida."""
    logger.info("Mensagem de %s: %s", user_phone, user_text)

    # ── 1. Extrair dados com IA ──────────────────────────────────
    try:
        flight_data = await extract_flight_info(user_text)
    except Exception:
        logger.exception("Erro ao chamar a IA")
        await send_whatsapp_text(
            user_phone,
            "Desculpe, tive um problema ao processar sua mensagem. Tente novamente.",
        )
        return

    if not flight_data:
        await send_whatsapp_text(
            user_phone,
            "Não consegui identificar um voo na sua mensagem.\n"
            "Tente algo como: *LA3244 amanhã* ou *GOL 1234 dia 20/03*",
        )
        return

    flight_iata = flight_data["flight_iata"]
    flight_date = flight_data["date"]
    logger.info("IA extraiu: voo=%s data=%s", flight_iata, flight_date)

    # ── 2. Validar se o voo existe na AviationStack ──────────────
    try:
        flight_info = await check_flight_existence(flight_iata)
    except Exception:
        logger.exception("Erro ao consultar AviationStack para %s", flight_iata)
        await send_whatsapp_text(
            user_phone,
            f"Não consegui verificar o voo *{flight_iata}* agora. "
            "Tente novamente em alguns instantes.",
        )
        return

    if not flight_info:
        await send_whatsapp_text(
            user_phone,
            f"O voo *{flight_iata}* não foi encontrado.\n"
            "Verifique o número e tente novamente (ex: *LA3244*, *G31234*).",
        )
        return

    # ── 3. Salvar no Supabase ────────────────────────────────────
    try:
        await add_subscription(user_phone, flight_iata, flight_date)
    except Exception:
        logger.exception("Erro ao salvar no Supabase")
        # Continua mesmo se falhar o banco — o usuário ainda recebe os dados

    # ── 4. Montar e enviar resposta ──────────────────────────────
    delay_text = ""
    if flight_info.get("delay") and flight_info["delay"] > 0:
        delay_text = f"\n⏱ *Atraso na partida:* {flight_info['delay']} min"

    reply = (
        f"✅ *Voo {flight_iata} encontrado e monitorado!*\n\n"
        f"✈️ *Companhia:* {flight_info['airline']}\n"
        f"📊 *Status:* {flight_info['status']}\n\n"
        f"🛫 *Partida:* {flight_info['departure_airport']} ({flight_info['departure_iata']})\n"
        f"   Horário: {flight_info['departure_scheduled']}\n"
        f"🛬 *Chegada:* {flight_info['arrival_airport']} ({flight_info['arrival_iata']})\n"
        f"   Horário: {flight_info['arrival_scheduled']}"
        f"{delay_text}\n\n"
        f"📅 *Data monitorada:* {flight_date}\n"
        f"Você receberá atualizações sobre este voo!"
    )
    await send_whatsapp_text(user_phone, reply)
    logger.info("Fluxo completo para %s -> %s", user_phone, flight_iata)
