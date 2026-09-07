-- Chat-Ledger schema
-- Multi-tenant, multi-platform, hash-partitioned by user_id (see build plan §6-7)

-- ── Canonical identity tables (NOT partitioned) ────────────────────────────

CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Links a platform account (Telegram chat_id / WhatsApp phone) to a canonical user.
-- Deliberately NOT partitioned: this table resolves platform_id -> user_id
-- BEFORE user_id is known, so partitioning it by user_id would force a full
-- scan on every incoming message.
CREATE TABLE user_identities (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    platform        TEXT NOT NULL CHECK (platform IN ('telegram', 'whatsapp')),
    platform_id     TEXT NOT NULL,          -- Telegram chat_id or WhatsApp phone number
    verified_phone  TEXT,                   -- populated once a verified number is captured
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, platform_id)
);

CREATE INDEX idx_user_identities_lookup ON user_identities (platform, platform_id);

-- ── Ledger tables (hash-partitioned by user_id) ────────────────────────────
-- Single-level HASH(user_id) only — NOT a composite hash on (user_id, id).
-- Every real query here filters on user_id alone, so this is what lets
-- Postgres prune to exactly one partition per query.

CREATE TABLE accounts (
    id          BIGSERIAL,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK (type IN ('asset', 'liability', 'income', 'expense')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, user_id)   -- partition key must be part of the PK
) PARTITION BY HASH (user_id);

CREATE TABLE journal_entries (
    id              BIGSERIAL,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    entry_date      TIMESTAMPTZ NOT NULL DEFAULT now(),
    narration       TEXT,
    raw_message     TEXT,
    source_platform TEXT,
    PRIMARY KEY (id, user_id)
) PARTITION BY HASH (user_id);

-- user_id is denormalized here (in addition to entry_id) purely so Postgres
-- can do a partition-wise join against journal_entries instead of shuffling
-- rows across partitions on every read.
CREATE TABLE entry_lines (
    id          BIGSERIAL,
    user_id     BIGINT NOT NULL,
    entry_id    BIGINT NOT NULL,
    account_id  BIGINT NOT NULL,
    dr_amt      NUMERIC(14,2),
    cr_amt      NUMERIC(14,2),
    PRIMARY KEY (id, user_id)
) PARTITION BY HASH (user_id);

-- NOTE: Postgres doesn't allow a simple FK from entry_lines.account_id ->
-- accounts.id when accounts' PK is composite (id, user_id). For this
-- starter schema, referential integrity between entry_lines/account_id/
-- entry_id is enforced in the application layer (app/db.py), not the DB.
-- Revisit with composite FKs (account_id, user_id) if you want DB-level
-- enforcement later.

-- ── Generate 16 hash partitions per table (power of 2, room to grow) ──────

DO $$
DECLARE
    i INT;
BEGIN
    FOR i IN 0..15 LOOP
        EXECUTE format(
            'CREATE TABLE accounts_p%1$s PARTITION OF accounts FOR VALUES WITH (MODULUS 16, REMAINDER %1$s)', i);
        EXECUTE format(
            'CREATE TABLE journal_entries_p%1$s PARTITION OF journal_entries FOR VALUES WITH (MODULUS 16, REMAINDER %1$s)', i);
        EXECUTE format(
            'CREATE TABLE entry_lines_p%1$s PARTITION OF entry_lines FOR VALUES WITH (MODULUS 16, REMAINDER %1$s)', i);
    END LOOP;
END $$;

-- ── Supporting indexes ──────────────────────────────────────────────────────

CREATE INDEX idx_accounts_user_id       ON accounts (user_id);
CREATE INDEX idx_accounts_user_name     ON accounts (user_id, name);
CREATE INDEX idx_journal_entries_user   ON journal_entries (user_id, entry_date);
CREATE INDEX idx_entry_lines_user_id    ON entry_lines (user_id);
CREATE INDEX idx_entry_lines_entry_id   ON entry_lines (entry_id);
