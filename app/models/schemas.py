from __future__ import annotations

from pydantic import BaseModel


# ── WhatsApp Webhook (entrada do Meta Cloud API) ──────────────────────
class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str


class WhatsAppMessage(BaseModel):
    from_: str  # telefone do remetente
    id: str
    timestamp: str
    type: str
    text: WhatsAppText | None = None

    class Config:
        populate_by_name = True
        fields = {"from_": {"alias": "from"}}


class WhatsAppText(BaseModel):
    body: str


class WhatsAppMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: list[WhatsAppContact] | None = None
    messages: list[WhatsAppMessage] | None = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: list[WhatsAppEntry]


# ── AviationStack ────────────────────────────────────────────────────
class FlightDeparture(BaseModel):
    airport: str | None = None
    iata: str | None = None
    scheduled: str | None = None
    estimated: str | None = None
    actual: str | None = None
    delay: int | None = None


class FlightArrival(BaseModel):
    airport: str | None = None
    iata: str | None = None
    scheduled: str | None = None
    estimated: str | None = None
    actual: str | None = None
    delay: int | None = None


class FlightAirline(BaseModel):
    name: str | None = None
    iata: str | None = None


class FlightInfo(BaseModel):
    flight_date: str | None = None
    flight_status: str | None = None
    departure: FlightDeparture
    arrival: FlightArrival
    airline: FlightAirline
    flight_number: str | None = None
    flight_iata: str | None = None


# ── Registro no Supabase ─────────────────────────────────────────────
class FlightRecord(BaseModel):
    user_phone: str
    flight_iata: str
    flight_status: str | None = None
    departure_airport: str | None = None
    arrival_airport: str | None = None
    scheduled_departure: str | None = None
    scheduled_arrival: str | None = None
