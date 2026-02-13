import logging

from supabase import create_client, Client

from app.config import settings
from app.models.schemas import FlightRecord

logger = logging.getLogger(__name__)

_supabase: Client | None = None

TABLE_NAME = "tracked_flights"


def _get_client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase


def save_flight(record: FlightRecord) -> dict:
    """Insere ou atualiza um registro de voo rastreado no Supabase."""
    client = _get_client()
    data = record.model_dump()

    result = (
        client.table(TABLE_NAME)
        .upsert(data, on_conflict="user_phone,flight_iata")
        .execute()
    )
    logger.info("Voo %s salvo para %s", record.flight_iata, record.user_phone)
    return result.data
