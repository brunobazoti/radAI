import json
import logging
import os
from datetime import date

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    return _openai_client


# ─────────────────────────────────────────────────────────────────────
# Passo 3 — Extrair informação de voo com IA
# ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""\
Você é um assistente especializado em extrair informações de voo de mensagens em linguagem natural.

REGRAS:
1. Identifique o código IATA da companhia aérea e o número do voo.
   Exemplos de conversão: "latam 3244" → "LA3244", "gol 1234" → "G31234",
   "azul 4567" → "AD4567", "american 100" → "AA100", "TAP 1234" → "TP1234".
2. Identifique a data do voo. Converta datas relativas para formato ISO (YYYY-MM-DD).
   Referência: a data de HOJE é {date.today().isoformat()}.
   "hoje" → data de hoje, "amanhã" → data de amanhã, "sexta" → próxima sexta-feira, etc.
3. Se não houver data explícita, assuma a data de HOJE.
4. Se NÃO conseguir identificar o voo, retorne null.

RESPONDA **APENAS** com JSON puro (sem markdown, sem ```):
- Sucesso: {{"flight_iata": "XX9999", "date": "YYYY-MM-DD"}}
- Falha: null
"""


async def extract_flight_info(user_message: str) -> dict | None:
    """
    Usa a OpenAI para interpretar a mensagem do usuário e extrair:
    - flight_iata: código IATA padronizado (ex: LA3244)
    - date: data do voo em formato YYYY-MM-DD

    Retorna None se não conseguir extrair.
    """
    client = _get_openai()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        max_tokens=60,
    )

    raw = response.choices[0].message.content.strip()
    logger.info("Resposta da IA: %s", raw)

    if raw.lower() == "null" or not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("IA retornou JSON inválido: %s", raw)
        return None

    if not isinstance(data, dict):
        return None
    if not data.get("flight_iata") or not data.get("date"):
        return None

    return {
        "flight_iata": data["flight_iata"].upper().strip(),
        "date": data["date"].strip(),
    }


# ─────────────────────────────────────────────────────────────────────
# Passo 4a — Verificar se o voo existe na AviationStack
# ─────────────────────────────────────────────────────────────────────

AVIATIONSTACK_URL = "http://api.aviationstack.com/v1/flights"


async def check_flight_existence(flight_iata: str) -> dict | None:
    """
    Consulta a AviationStack para verificar se o voo existe.

    Retorna um dict com os dados do voo se encontrado, ou None.
    A free tier da AviationStack só aceita HTTP (não HTTPS).
    """
    params = {
        "access_key": os.getenv("AVIATIONSTACK_KEY", ""),
        "flight_iata": flight_iata.upper(),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(AVIATIONSTACK_URL, params=params)
        resp.raise_for_status()

    payload = resp.json()

    if payload.get("error"):
        logger.error("Erro AviationStack: %s", payload["error"])
        return None

    flights = payload.get("data")
    if not flights:
        return None

    flight = flights[0]
    dep = flight.get("departure", {})
    arr = flight.get("arrival", {})

    return {
        "airline": flight.get("airline", {}).get("name", "N/A"),
        "flight_iata": flight.get("flight", {}).get("iata", flight_iata),
        "status": flight.get("flight_status", "unknown"),
        "departure_airport": dep.get("airport", "N/A"),
        "departure_iata": dep.get("iata", ""),
        "departure_scheduled": dep.get("scheduled", "N/A"),
        "arrival_airport": arr.get("airport", "N/A"),
        "arrival_iata": arr.get("iata", ""),
        "arrival_scheduled": arr.get("scheduled", "N/A"),
        "delay": dep.get("delay"),
    }


# ─────────────────────────────────────────────────────────────────────
# Passo 4b — Enviar mensagem de texto via WhatsApp (Meta Cloud API)
# ─────────────────────────────────────────────────────────────────────

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0/{phone_id}/messages"


async def send_whatsapp_text(to: str, body: str) -> None:
    """
    Envia uma mensagem de texto simples para o número 'to'
    usando a Meta Cloud API (WhatsApp Business).
    """
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    token = os.getenv("WHATSAPP_TOKEN", "")
    url = WHATSAPP_API_URL.format(phone_id=phone_id)

    headers = {
        "Authorization": f"Bearer {token}",
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
        logger.error("Erro ao enviar WhatsApp: %s — %s", resp.status_code, resp.text)
        resp.raise_for_status()

    logger.info("Mensagem enviada para %s", to)
