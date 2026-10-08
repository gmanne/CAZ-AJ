-- CareAtZero database schema
-- Mirrors the data model in the Project Blueprint, section 6.4

CREATE TABLE IF NOT EXISTS sources (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    source_type     TEXT NOT NULL,      -- e.g. HRSA, free_clinic_network, local_nonprofit
    last_checked    TEXT NOT NULL,      -- ISO 8601 timestamp
    status          TEXT NOT NULL DEFAULT 'active'  -- active | stale | unavailable
);

CREATE TABLE IF NOT EXISTS care_sites (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,      -- permanent | mobile | pop_up
    address         TEXT,
    latitude        REAL,
    longitude       REAL,
    services        TEXT NOT NULL,      -- comma-separated: medical,dental,vision,behavioral
    cost_class      TEXT NOT NULL,      -- Free | Very Low Cost | Sliding Scale | Unknown
    eligibility     TEXT,
    uninsured_accepted INTEGER DEFAULT 1,   -- boolean 0/1
    appointment_rule TEXT,              -- walk_in | appointment_required | either
    documents_needed TEXT,
    phone           TEXT,
    website         TEXT,
    source_id       TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS care_events (
    id              TEXT PRIMARY KEY,
    provider_id     TEXT,               -- optional link to a care_sites row
    name            TEXT NOT NULL,
    date            TEXT NOT NULL,      -- ISO 8601 date
    start_time      TEXT,
    end_time        TEXT,
    address         TEXT,
    latitude        REAL,
    longitude       REAL,
    services        TEXT NOT NULL,
    cost_class      TEXT NOT NULL,
    eligibility     TEXT,
    appointment_rule TEXT,
    documents_needed TEXT,
    source_id       TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS search_profile (
    id              TEXT PRIMARY KEY,
    service         TEXT NOT NULL,
    location        TEXT NOT NULL,      -- ZIP or "lat,lon"
    age_group       TEXT,
    insurance_status TEXT,
    income_band     TEXT,
    timing          TEXT NOT NULL,      -- today | this_week | flexible
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saved_care (
    id              TEXT PRIMARY KEY,
    care_record_id  TEXT NOT NULL,
    record_type     TEXT NOT NULL,      -- site | event
    note            TEXT,
    saved_at        TEXT NOT NULL
);
