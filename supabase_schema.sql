-- Execute este SQL no Supabase SQL Editor para criar a tabela
CREATE TABLE IF NOT EXISTS tracked_flights (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_phone      TEXT NOT NULL,
    flight_iata     TEXT NOT NULL,
    flight_status   TEXT,
    departure_airport TEXT,
    arrival_airport   TEXT,
    scheduled_departure TEXT,
    scheduled_arrival   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE (user_phone, flight_iata)
);

-- Índice para buscas por telefone
CREATE INDEX IF NOT EXISTS idx_tracked_flights_user_phone
    ON tracked_flights (user_phone);

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_tracked_flights_updated_at
    BEFORE UPDATE ON tracked_flights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
