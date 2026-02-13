import re

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None

# Regex simples para códigos IATA de voo (2 letras + 1-4 dígitos)
_FLIGHT_CODE_RE = re.compile(r"\b([A-Z]{2})\s*(\d{1,4})\b", re.IGNORECASE)

SYSTEM_PROMPT = (
    "Você é um assistente que extrai números de voo de mensagens de usuários. "
    "Retorne APENAS o código IATA do voo no formato XX9999 (ex: LA3456, G31234, AA100). "
    "Se não encontrar nenhum número de voo, retorne exatamente: NONE"
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def extract_flight_code_regex(text: str) -> str | None:
    """Tenta extrair o código de voo via regex antes de chamar a LLM."""
    match = _FLIGHT_CODE_RE.search(text)
    if match:
        return f"{match.group(1).upper()}{match.group(2)}"
    return None


async def extract_flight_code(text: str) -> str | None:
    """Extrai o código de voo da mensagem do usuário.

    1. Tenta via regex (rápido e gratuito).
    2. Se falhar, usa a OpenAI como fallback.
    """
    code = extract_flight_code_regex(text)
    if code:
        return code

    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=20,
    )
    result = response.choices[0].message.content.strip().upper()
    if result == "NONE" or not result:
        return None

    # Valida que o resultado parece um código IATA
    clean = re.sub(r"\s+", "", result)
    if re.fullmatch(r"[A-Z]{2}\d{1,4}", clean):
        return clean
    return None
