import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, Response

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Flight Tracker", version="0.1.0")


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


# ── POST /webhook — Receber mensagens ────────────────────────────────
@app.post("/webhook")
async def receive_message(request: Request):
    """
    Recebe o payload JSON do WhatsApp.
    Por enquanto, apenas loga no terminal e retorna 200 OK.
    """
    body = await request.json()
    logger.info("Payload recebido:\n%s", json.dumps(body, indent=2, ensure_ascii=False))
    return {"status": "ok"}
