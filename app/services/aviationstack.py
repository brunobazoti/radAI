import httpx

from app.config import settings
from app.models.schemas import FlightArrival, FlightDeparture, FlightAirline, FlightInfo

AVIATIONSTACK_BASE_URL = "http://api.aviationstack.com/v1"


async def get_flight_info(flight_iata: str) -> FlightInfo | None:
    """Consulta a AviationStack pelo código IATA do voo (ex: LA3456)."""
    params = {
        "access_key": settings.aviationstack_api_key,
        "flight_iata": flight_iata.upper(),
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{AVIATIONSTACK_BASE_URL}/flights", params=params)
        resp.raise_for_status()

    data = resp.json()

    if not data.get("data"):
        return None

    flight = data["data"][0]
    dep = flight.get("departure", {})
    arr = flight.get("arrival", {})
    airline = flight.get("airline", {})

    return FlightInfo(
        flight_date=flight.get("flight_date"),
        flight_status=flight.get("flight_status"),
        departure=FlightDeparture(
            airport=dep.get("airport"),
            iata=dep.get("iata"),
            scheduled=dep.get("scheduled"),
            estimated=dep.get("estimated"),
            actual=dep.get("actual"),
            delay=dep.get("delay"),
        ),
        arrival=FlightArrival(
            airport=arr.get("airport"),
            iata=arr.get("iata"),
            scheduled=arr.get("scheduled"),
            estimated=arr.get("estimated"),
            actual=arr.get("actual"),
            delay=arr.get("delay"),
        ),
        airline=FlightAirline(
            name=airline.get("name"),
            iata=airline.get("iata"),
        ),
        flight_number=flight.get("flight", {}).get("number"),
        flight_iata=flight.get("flight", {}).get("iata"),
    )
