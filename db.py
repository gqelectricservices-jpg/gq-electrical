#!/usr/bin/env python3
"""SQLite schema and connection helpers for GQ Electrical Services. No demo data."""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
TZ = ZoneInfo("America/New_York")
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "gq.db"


def dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def get_conn(path: Path | None = None) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path or DB_PATH), check_same_thread=False)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  company_name TEXT NOT NULL,
  license_no TEXT,
  phone TEXT,
  email TEXT,
  street TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  service_area TEXT,
  default_labor_rate REAL,
  tax_rate REAL,
  invoice_footer TEXT,
  next_quote_no INTEGER NOT NULL DEFAULT 1001,
  next_job_no INTEGER NOT NULL DEFAULT 2001,
  next_invoice_no INTEGER NOT NULL DEFAULT 3001,
  tagline TEXT,
  location_line TEXT,
  hero_headline TEXT,
  hero_subhead TEXT,
  about_blurb TEXT,
  warranty TEXT,
  rate_card TEXT
);

CREATE TABLE IF NOT EXISTS team (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  color TEXT,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'person',
  phone TEXT,
  email TEXT,
  notes TEXT,
  source TEXT NOT NULL DEFAULT 'shop',
  portal_code TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS addresses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  label TEXT,
  street TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'FL',
  zip TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit TEXT NOT NULL DEFAULT 'ea',
  qty_on_hand REAL NOT NULL DEFAULT 0,
  unit_cost REAL NOT NULL DEFAULT 0,
  reorder_level REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  number TEXT NOT NULL UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  address_id INTEGER REFERENCES addresses(id),
  status TEXT NOT NULL DEFAULT 'draft',
  notes TEXT,
  tax_rate REAL NOT NULL,
  created_at TEXT NOT NULL,
  valid_until TEXT
);

CREATE TABLE IF NOT EXISTS quote_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  description TEXT NOT NULL,
  qty REAL NOT NULL DEFAULT 1,
  unit TEXT DEFAULT 'ea',
  unit_price REAL NOT NULL DEFAULT 0,
  inventory_id INTEGER REFERENCES inventory(id)
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  number TEXT NOT NULL UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  address_id INTEGER REFERENCES addresses(id),
  quote_id INTEGER REFERENCES quotes(id),
  job_type TEXT NOT NULL DEFAULT 'service_call',
  status TEXT NOT NULL DEFAULT 'scheduled',
  tech_id INTEGER REFERENCES team(id),
  scheduled_date TEXT,
  scheduled_start TEXT,
  scheduled_end TEXT,
  scope TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS job_materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  inventory_id INTEGER REFERENCES inventory(id),
  description TEXT NOT NULL,
  qty REAL NOT NULL,
  unit TEXT,
  unit_cost REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  number TEXT NOT NULL UNIQUE,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  job_id INTEGER REFERENCES jobs(id),
  address_id INTEGER REFERENCES addresses(id),
  status TEXT NOT NULL DEFAULT 'unpaid',
  tax_rate REAL NOT NULL,
  issued_at TEXT NOT NULL,
  due_date TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS invoice_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  description TEXT NOT NULL,
  qty REAL NOT NULL DEFAULT 1,
  unit_price REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  amount REAL NOT NULL,
  method TEXT NOT NULL,
  paid_at TEXT NOT NULL,
  reference TEXT
);

CREATE TABLE IF NOT EXISTS web_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  street TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  service TEXT,
  message TEXT,
  preferred TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL
);
"""


def next_number(conn: sqlite3.Connection, kind: str) -> str:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if kind == "quote":
        n = row["next_quote_no"]
        conn.execute("UPDATE settings SET next_quote_no = ? WHERE id = 1", (n + 1,))
        return f"Q-{n}"
    if kind == "job":
        n = row["next_job_no"]
        conn.execute("UPDATE settings SET next_job_no = ? WHERE id = 1", (n + 1,))
        return f"J-{n}"
    n = row["next_invoice_no"]
    conn.execute("UPDATE settings SET next_invoice_no = ? WHERE id = 1", (n + 1,))
    return f"INV-{n}"



def _table_cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def new_portal_code(conn: sqlite3.Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(30):
        code = "GQ-" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not conn.execute("SELECT 1 FROM customers WHERE portal_code = ?", (code,)).fetchone():
            return code
    return "GQ-" + secrets.token_hex(3).upper()


SITE_DEFAULTS = {
    "company_name": "GQ Electrical Services LLC",
    "license_no": "ER13016834",
    "phone": "(689) 500-6543",
    "email": "Services@gqelectrical.com",
    "street": "2207 Plantation Lakes Cir",
    "city": "Sanford",
    "state": "FL",
    "zip": "32771",
    "service_area": "Orange, Lake, Volusia, and Seminole Counties",
    "tagline": "Where Guaranteed Meets Quality.",
    "location_line": "Sanford, Florida",
    "hero_headline": "Electrical for houses that notice.",
    "hero_subhead": (
        "Lighting, power, and charging — installed with the same care you'd expect from any other trade in the house."
    ),
    "about_blurb": (
        "We focus on residential new construction, service calls for existing homes, and renovations "
        "across Seminole, Orange, Volusia, and Lake Counties. Clear scope. Clean finish.\n\n"
        "Licensed and insured in Florida. Ready for residential builders and homeowners across Central Florida."
    ),
}


# Owner's rate card, exactly as given. Stored only; nothing auto-prices from it yet.
RATE_CARD = {
    "lines": [
        "Solo service: $190 for the drive and the first hour; $160 each hour after",
        "Pair on service or a custom house: $260 an hour flat",
        "Materials: at cost plus 30%",
        "Diagnostic trip: the $190, credited if they hire us the same visit",
        "Planned quotes: free",
        "Permit: on its own line at the county fee, plus $150 handling, or $250 on a service change",
        "Tract houses, rough and trim: $6.50/sq ft if the builder supplies the lights; billed 60% after rough inspection and 40% after final",
        "$7.50/sq ft only if we supply a cheap builder-grade light package",
        "Any other light list: cost plus 30% on top of the $6.50",
        "Price good for 30 days",
    ],
    "solo_service": {"drive_and_first_hour": 190.00, "each_additional_hour": 160.00},
    "pair_or_custom_house_hourly": 260.00,
    "materials_markup_pct": 30,
    "diagnostic_trip": {"fee": 190.00, "credited_if_hired_same_visit": True},
    "planned_quote_fee": 0,
    "permit": {
        "county_fee": "pass-through, own line",
        "handling": 150.00,
        "handling_service_change": 250.00,
    },
    "tract_rough_and_trim": {
        "per_sqft_builder_supplies_lights": 6.50,
        "per_sqft_we_supply_builder_grade_package": 7.50,
        "other_light_list": "base $6.50/sq ft plus light list at cost plus 30%",
        "billing": {"after_rough_inspection_pct": 60, "after_final_pct": 40},
    },
    "quote_valid_days": 30,
}
RATE_CARD_JSON = json.dumps(RATE_CARD)


def migrate(conn: sqlite3.Connection) -> None:
    cols = _table_cols(conn, "customers")
    if "source" not in cols:
        conn.execute("ALTER TABLE customers ADD COLUMN source TEXT NOT NULL DEFAULT 'shop'")
    if "portal_code" not in cols:
        conn.execute("ALTER TABLE customers ADD COLUMN portal_code TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS web_requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
          name TEXT NOT NULL,
          phone TEXT,
          email TEXT,
          street TEXT,
          city TEXT,
          state TEXT,
          zip TEXT,
          service TEXT,
          message TEXT,
          preferred TEXT,
          status TEXT NOT NULL DEFAULT 'new',
          created_at TEXT NOT NULL
        );
        """
    )
    # Website / marketing fields on settings
    scols = _table_cols(conn, "settings")
    for col, decl in [
        ("tagline", "TEXT"),
        ("location_line", "TEXT"),
        ("hero_headline", "TEXT"),
        ("hero_subhead", "TEXT"),
        ("about_blurb", "TEXT"),
        ("warranty", "TEXT"),
        ("rate_card", "TEXT"),
    ]:
        if col not in scols:
            conn.execute(f"ALTER TABLE settings ADD COLUMN {col} {decl}")
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if row:
        # Fill empty website fields with the approved public copy
        for key in ("tagline", "location_line", "hero_headline", "hero_subhead", "about_blurb"):
            if not (row.get(key) or "").strip():
                conn.execute(f"UPDATE settings SET {key} = ? WHERE id = 1", (SITE_DEFAULTS[key],))
        if not (row.get("rate_card") or "").strip():
            conn.execute("UPDATE settings SET rate_card = ? WHERE id = 1", (RATE_CARD_JSON,))
    _relax_price_columns(conn)
    conn.commit()


def _relax_price_columns(conn: sqlite3.Connection) -> None:
    """Older DBs had NOT NULL price defaults (labor 125, tax 7%). Rebuild settings so blank stays blank."""
    info = {r["name"]: r for r in conn.execute("PRAGMA table_info(settings)")}
    lab = info.get("default_labor_rate")
    if not lab or not lab["notnull"]:
        return
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(settings)")]
    conn.execute("ALTER TABLE settings RENAME TO settings_old")
    settings_sql = SCHEMA.split("CREATE TABLE IF NOT EXISTS team")[0]
    conn.executescript(settings_sql)
    keep = [c for c in cols if c in {r["name"] for r in conn.execute("PRAGMA table_info(settings)")}]
    cl = ", ".join(keep)
    conn.execute(f"INSERT INTO settings ({cl}) SELECT {cl} FROM settings_old")
    conn.execute("DROP TABLE settings_old")


# Fresh database starts with the owner only. No phone until he enters it.
TEAM = [
    ("Gerard Alberta", "owner", None, None, "#c9922a"),
]

def init_db(conn: sqlite3.Connection) -> None:
    """Create an empty schema. Only the company settings row (and existing team list) is written; no sample records."""
    conn.executescript(SCHEMA)
    conn.commit()
    has = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"]
    if has == 0:
        conn.execute(
            """
            INSERT INTO settings (
              id, company_name, license_no, phone, email, street, city, state, zip, service_area,
              tagline, location_line, hero_headline, hero_subhead, about_blurb, rate_card
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(
                SITE_DEFAULTS[k]
                for k in (
                    "company_name", "license_no", "phone", "email", "street", "city", "state", "zip",
                    "service_area", "tagline", "location_line", "hero_headline", "hero_subhead", "about_blurb",
                )
            )
            + (RATE_CARD_JSON,),
        )
        if conn.execute("SELECT COUNT(*) AS c FROM team").fetchone()["c"] == 0:
            for t in TEAM:
                conn.execute(
                    "INSERT INTO team (name, role, phone, email, color, active) VALUES (?,?,?,?,?,1)", t
                )
        conn.commit()
    migrate(conn)
