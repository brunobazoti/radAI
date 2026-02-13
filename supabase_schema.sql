-- =============================================================
-- Execute este script no SQL Editor do Supabase (supabase.com)
-- =============================================================

CREATE TABLE IF NOT EXISTS flight_subscriptions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_phone      TEXT    NOT NULL,
    flight_iata     TEXT    NOT NULL,
    flight_date     DATE    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ      DEFAULT now()
);

-- Evita que o mesmo usuário rastreie o mesmo voo+data duas vezes
CREATE UNIQUE INDEX IF NOT EXISTS uq_phone_flight_date
    ON flight_subscriptions (user_phone, flight_iata, flight_date);

-- Índice para buscas por telefone (listar voos de um usuário)
CREATE INDEX IF NOT EXISTS idx_fs_user_phone
    ON flight_subscriptions (user_phone);
