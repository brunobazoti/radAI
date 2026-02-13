import logging
import os

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_supabase: Client | None = None


def _get_client() -> Client:
    """Inicializa o client Supabase uma única vez (lazy singleton)."""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        _supabase = create_client(url, key)
    return _supabase


async def add_subscription(phone: str, flight_iata: str, flight_date: str) -> dict:
    """
    Salva uma assinatura de rastreamento na tabela flight_subscriptions.

    Args:
        phone:        Telefone do usuário (ex: '5511999999999')
        flight_iata:  Código IATA do voo (ex: 'LA3244')
        flight_date:  Data do voo no formato 'YYYY-MM-DD'

    Returns:
        Dicionário com os dados inseridos.
    """
    client = _get_client()

    row = {
        "user_phone": phone,
        "flight_iata": flight_iata.upper(),
        "flight_date": flight_date,
        "status": "active",
    }

    result = (
        client.table("flight_subscriptions")
        .upsert(row, on_conflict="user_phone,flight_iata,flight_date")
        .execute()
    )

    logger.info(
        "Subscription salva: %s -> %s (%s)", phone, flight_iata, flight_date
    )
    return result.data[0] if result.data else row
