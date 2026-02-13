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
        "gate": dep.get("gate"),
        "baggage": arr.get("baggage"),
    }


# ─────────────────────────────────────────────────────────────────────
# Mapeamento de status de voo → template do WhatsApp
# ─────────────────────────────────────────────────────────────────────

FLIGHT_TEMPLATES: dict[str, dict] = {
    "tracking_start": {
        "template_name": "flight_tracking_start",
        "param_keys": ["nome_usuario", "numero_voo", "data_voo"],
    },
    "tracking_stop": {
        "template_name": "flight_tracking_stop",
        "param_keys": ["numero_voo"],
    },
    "delayed": {
        "template_name": "flight_delay_alert",
        "param_keys": ["nome_usuario", "numero_voo", "novo_horario", "tempo_atraso"],
    },
    "gate_change": {
        "template_name": "flight_gate_change",
        "param_keys": ["numero_voo", "novo_portao"],
    },
    "boarding": {
        "template_name": "flight_boarding_start",
        "param_keys": ["nome_usuario", "numero_voo", "portao"],
    },
    "landed": {
        "template_name": "flight_landed_confirm",
        "param_keys": ["numero_voo", "aeroporto_destino", "horario_pouso", "esteira"],
    },
    "cancelled": {
        "template_name": "flight_cancelled_alert",
        "param_keys": ["nome_usuario", "numero_voo", "data_original"],
    },
}


def get_template_for_status(status: str) -> dict | None:
    """
    Retorna o dict de configuração do template para um status de voo.

    Exemplo:
        info = get_template_for_status("delayed")
        # {"template_name": "flight_delay_alert", "param_keys": [...]}

    Retorna None se o status não tiver template mapeado.
    """
    return FLIGHT_TEMPLATES.get(status)


def build_template_params(status: str, data: dict) -> tuple[str, list[str]] | None:
    """
    Dado um status e um dicionário de dados, retorna (template_name, [params])
    prontos para passar ao whatsapp_api.send_template().

    Args:
        status: Chave do status (ex: 'tracking_start', 'delayed', 'landed')
        data:   Dict com os valores; as chaves devem corresponder a param_keys.

    Retorna None se o status não tiver template.
    """
    tpl = FLIGHT_TEMPLATES.get(status)
    if not tpl:
        logger.warning("Nenhum template mapeado para status: %s", status)
        return None

    params = [str(data.get(k, "N/A")) for k in tpl["param_keys"]]
    return tpl["template_name"], params
