#!/usr/bin/env python3
"""SQLite schema, connection helpers, and realistic demo seed for GQ Electrical Services."""
from __future__ import annotations

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
  default_labor_rate REAL NOT NULL DEFAULT 125,
  tax_rate REAL NOT NULL DEFAULT 0.07,
  invoice_footer TEXT,
  next_quote_no INTEGER NOT NULL DEFAULT 1001,
  next_job_no INTEGER NOT NULL DEFAULT 2001,
  next_invoice_no INTEGER NOT NULL DEFAULT 3001,
  tagline TEXT,
  location_line TEXT,
  hero_headline TEXT,
  hero_subhead TEXT,
  about_blurb TEXT
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
    "company_name": "GQ Electrical Services",
    "license_no": "ER13016834",
    "phone": "+1 (689) 500-6543",
    "email": "Services@gqelectrical.com",
    "street": "2207 Plantation Lakes Cir",
    "city": "Sanford",
    "state": "FL",
    "zip": "32771",
    "service_area": "Seminole, Orange, Volusia, and Lake Counties — and surrounding Central Florida",
    "tax_rate": 0.07,
    "invoice_footer": (
        "Thank you for trusting GQ Electrical Services. Payment is due on completion, per the quote terms. "
        "Make checks payable to GQ Electrical Services. Questions: +1 (689) 500-6543. "
        "Licensed & insured — Florida Electrical Contractor License ER13016834."
    ),
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
    ]:
        if col not in scols:
            conn.execute(f"ALTER TABLE settings ADD COLUMN {col} {decl}")
    # Move company Settings from Westfield NJ → Sanford FL when still on old seed
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if row and (row.get("city") == "Westfield" or row.get("state") == "NJ"):
        conn.execute(
            """
            UPDATE settings SET
              license_no = ?, phone = ?, street = ?, city = ?, state = ?, zip = ?,
              service_area = ?, tax_rate = ?, invoice_footer = ?,
              tagline = COALESCE(NULLIF(tagline, ''), ?),
              location_line = COALESCE(NULLIF(location_line, ''), ?),
              hero_headline = COALESCE(NULLIF(hero_headline, ''), ?),
              hero_subhead = COALESCE(NULLIF(hero_subhead, ''), ?),
              about_blurb = COALESCE(NULLIF(about_blurb, ''), ?)
            WHERE id = 1
            """,
            (
                SITE_DEFAULTS["license_no"],
                SITE_DEFAULTS["phone"],
                SITE_DEFAULTS["street"],
                SITE_DEFAULTS["city"],
                SITE_DEFAULTS["state"],
                SITE_DEFAULTS["zip"],
                SITE_DEFAULTS["service_area"],
                SITE_DEFAULTS["tax_rate"],
                SITE_DEFAULTS["invoice_footer"],
                SITE_DEFAULTS["tagline"],
                SITE_DEFAULTS["location_line"],
                SITE_DEFAULTS["hero_headline"],
                SITE_DEFAULTS["hero_subhead"],
                SITE_DEFAULTS["about_blurb"],
            ),
        )
    elif row:
        # Fill empty website fields with Sanford defaults
        for key in ("tagline", "location_line", "hero_headline", "hero_subhead", "about_blurb"):
            if not (row.get(key) or "").strip():
                conn.execute(f"UPDATE settings SET {key} = ? WHERE id = 1", (SITE_DEFAULTS[key],))
        # Upgrade outdated public seed (old EC license, 100 E 1st, civic/owner copy)
        street = (row.get("street") or "").strip()
        lic = (row.get("license_no") or "").strip()
        about = row.get("about_blurb") or ""
        needs_copy = (
            street == "100 E 1st Street"
            or lic == "EC13004567"
            or "occasional civic" in about
            or "Gerard Alberta" in about
        )
        if needs_copy:
            conn.execute(
                """
                UPDATE settings SET
                  license_no = ?, phone = ?, email = ?, street = ?, city = ?, state = ?, zip = ?,
                  service_area = ?, invoice_footer = ?, about_blurb = ?
                WHERE id = 1
                """,
                (
                    SITE_DEFAULTS["license_no"],
                    SITE_DEFAULTS["phone"],
                    SITE_DEFAULTS["email"],
                    SITE_DEFAULTS["street"],
                    SITE_DEFAULTS["city"],
                    SITE_DEFAULTS["state"],
                    SITE_DEFAULTS["zip"],
                    SITE_DEFAULTS["service_area"],
                    SITE_DEFAULTS["invoice_footer"],
                    SITE_DEFAULTS["about_blurb"],
                ),
            )
    conn.commit()


DEMO_PORTAL_CODES = {
    1: "GQ-BRENN1",
    2: "GQ-MAPLE2",
    3: "GQ-ORTIZ3",
    4: "GQ-HARR04",
    5: "GQ-DEAC05",
    6: "GQ-CHO662",
    7: "GQ-LAKE07",
    8: "GQ-MORE08",
}


def ensure_public_demo(conn: sqlite3.Connection) -> None:
    """Assign portal codes and seed 1–2 web requests without wiping existing customers."""
    now = datetime.now(TZ).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    for cid, code in DEMO_PORTAL_CODES.items():
        row = conn.execute("SELECT id, portal_code FROM customers WHERE id = ?", (cid,)).fetchone()
        if row and not row["portal_code"]:
            conn.execute("UPDATE customers SET portal_code = ? WHERE id = ?", (code, cid))
    for row in conn.execute(
        "SELECT id FROM customers WHERE portal_code IS NULL OR portal_code = ''"
    ).fetchall():
        conn.execute(
            "UPDATE customers SET portal_code = ? WHERE id = ?",
            (new_portal_code(conn), row["id"]),
        )

    n = conn.execute("SELECT COUNT(*) AS c FROM web_requests").fetchone()["c"]
    if n == 0:
        # Claire Whitmore — lighting consult
        cur = conn.execute(
            """INSERT INTO customers (name, kind, phone, email, notes, source, portal_code, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "Claire Whitmore",
                "person",
                "(908) 555-4190",
                "claire.whitmore@icloud.com",
                "Web request — lighting. Interested in picture lights and dimmable cans in the living room. Prefers weekday mornings.",
                "web",
                "GQ-WHIT28",
                now,
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
            (cid, "Home", "412 Park Avenue", "Sanford", "FL", "32771"),
        )
        conn.execute(
            """INSERT INTO web_requests (
                 customer_id, name, phone, email, street, city, state, zip,
                 service, message, preferred, status, created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                "Claire Whitmore",
                "(908) 555-4190",
                "claire.whitmore@icloud.com",
                "412 Park Avenue",
                "Sanford",
                "FL",
                "32771",
                "lighting",
                "Looking for picture lights over two canvases and to replace the living-room cans with something dimmable and quiet. The house is a 1920s colonial — we would rather not see the work.",
                "Weekday mornings",
                "new",
                now,
            ),
        )
        # Daniel Lang — panel / whole-home
        cur = conn.execute(
            """INSERT INTO customers (name, kind, phone, email, notes, source, portal_code, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "Daniel Lang",
                "person",
                "(908) 555-3388",
                "dlang@protonmail.com",
                "Web request — panel & whole-home. Considering 200A upgrade and whole-house surge before a kitchen remodel.",
                "web",
                "GQ-LANG44",
                now,
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
            (cid, "Home", "88 Lake Mary Blvd", "Lake Mary", "FL", "32746"),
        )
        conn.execute(
            """INSERT INTO web_requests (
                 customer_id, name, phone, email, street, city, state, zip,
                 service, message, preferred, status, created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                "Daniel Lang",
                "(908) 555-3388",
                "dlang@protonmail.com",
                "88 Lake Mary Blvd",
                "Lake Mary",
                "FL",
                "32746",
                "panel",
                "Fuse box is original to the house. Kitchen remodel is scheduled for the fall and the architect asked about a 200A service and whole-house surge. Would like someone to look before we lock the drawings.",
                "Evenings or Saturday",
                "new",
                now,
            ),
        )
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)
    has = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"]
    if has == 0:
        seed(conn)
    ensure_public_demo(conn)


def _iso(d: date | datetime) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S")
    return d.isoformat()


def seed(conn: sqlite3.Connection) -> None:
    today = datetime.now(TZ).date()
    now = datetime.now(TZ).replace(tzinfo=None, microsecond=0)

    def ago(days: int, hours: int = 9) -> str:
        dt = datetime.combine(today - timedelta(days=days), datetime.min.time()).replace(hour=hours)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    def day_offset(n: int) -> str:
        return (today + timedelta(days=n)).isoformat()

    conn.execute(
        """
        INSERT INTO settings (
          id, company_name, license_no, phone, email, street, city, state, zip,
          service_area, default_labor_rate, tax_rate, invoice_footer,
          next_quote_no, next_job_no, next_invoice_no,
          tagline, location_line, hero_headline, hero_subhead, about_blurb
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            SITE_DEFAULTS["company_name"],
            SITE_DEFAULTS["license_no"],
            SITE_DEFAULTS["phone"],
            SITE_DEFAULTS["email"],
            SITE_DEFAULTS["street"],
            SITE_DEFAULTS["city"],
            SITE_DEFAULTS["state"],
            SITE_DEFAULTS["zip"],
            SITE_DEFAULTS["service_area"],
            125.0,
            SITE_DEFAULTS["tax_rate"],
            SITE_DEFAULTS["invoice_footer"],
            1008,
            2006,
            3005,
            SITE_DEFAULTS["tagline"],
            SITE_DEFAULTS["location_line"],
            SITE_DEFAULTS["hero_headline"],
            SITE_DEFAULTS["hero_subhead"],
            SITE_DEFAULTS["about_blurb"],
        ),
    )

    techs = [
        ("Gerard Alberta", "owner", "(407) 555-0144", "gerard@gqelectrical.com", "#c9922a"),
        ("Marcus Hale", "technician", "(908) 555-0171", "marcus@gqelectrical.com", "#1c3a5f"),
        ("Devon Price", "technician", "(908) 555-0172", "devon@gqelectrical.com", "#2d6a4f"),
        ("Sofia Reyes", "technician", "(908) 555-0173", "sofia@gqelectrical.com", "#7c2d12"),
        ("Kim Ellison", "office", "(908) 555-0145", "kim@gqelectrical.com", "#5c5852"),
    ]
    for t in techs:
        conn.execute(
            "INSERT INTO team (name, role, phone, email, color, active) VALUES (?,?,?,?,?,1)",
            t,
        )

    customers = [
        (
            "Patricia Brennan",
            "person",
            "(908) 555-2201",
            "pbrennan@verizon.net",
            "Homeowner. 1978 split-level. Interested in whole-house surge and generator later.",
            ago(48),
        ),
        (
            "Maplewood Veterinary Clinic",
            "business",
            "(973) 555-4410",
            "facilities@maplewoodvet.com",
            "Office manager: Dana Whitlock. After-hours work preferred. Need to keep surgery suite live.",
            ago(32),
        ),
        (
            "James & Elena Ortiz",
            "person",
            "(908) 555-8834",
            "j.ortiz@gmail.com",
            "Tesla Model Y. Existing 200A service. Prefers morning arrival.",
            ago(21),
        ),
        (
            "Harrington Property Group",
            "business",
            "(973) 555-7002",
            "ops@harringtonpg.com",
            "Property manager: Chris Harrington. Three rental buildings. Net-15 on paper, slow to pay.",
            ago(90),
        ),
        (
            "Deacon Hill Baptist Church",
            "business",
            "(908) 555-3318",
            "trustees@deaconhill.org",
            "Trustee contact: Rev. Calvin Moore. Need quiet work around choir practice Wed evenings.",
            ago(10),
        ),
        (
            "Ryan Cho",
            "person",
            "(908) 555-6620",
            "ryan.cho@icloud.com",
            "Flickering kitchen cans. Easy access. Paid promptly last time.",
            ago(14),
        ),
        (
            "Lakeside Condominium Association",
            "business",
            "(732) 555-1904",
            "board@lakesidecondo.org",
            "Board treasurer: Marlene Voss. Common-area work only. Need COI on file.",
            ago(40),
        ),
        (
            "Angela Moretti",
            "person",
            "(908) 555-2744",
            "amoretti@outlook.com",
            "New addition over garage. GC is Brennan Builders. Rough-in this week, trim later.",
            ago(18),
        ),
    ]
    for c in customers:
        conn.execute(
            "INSERT INTO customers (name, kind, phone, email, notes, created_at) VALUES (?,?,?,?,?,?)",
            c,
        )

    addresses = [
        (1, "Home", "14 Oak Lane", "Westfield", "NJ", "07090"),
        (2, "Clinic", "220 Baker Street", "Maplewood", "NJ", "07040"),
        (3, "Home", "88 Brookside Drive", "Cranford", "NJ", "07016"),
        (4, "Building A — 12 Elm", "12 Elm Street", "Elizabeth", "NJ", "07201"),
        (4, "Building B — 40 High", "40 High Street", "Elizabeth", "NJ", "07202"),
        (4, "Building C — 9 Grove", "9 Grove Place", "Roselle", "NJ", "07203"),
        (5, "Sanctuary", "1 Church Road", "Springfield", "NJ", "07081"),
        (6, "Home", "5 Cedar Court", "Mountainside", "NJ", "07092"),
        (7, "Clubhouse / common", "400 Lakeside Avenue", "Rahway", "NJ", "07065"),
        (8, "Residence / addition", "19 Prospect Avenue", "Summit", "NJ", "07901"),
    ]
    for a in addresses:
        conn.execute(
            "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
            a,
        )

    inventory = [
        ("NM-12250", "12/2 NM-B w/ ground", "wire", "ft", 850, 0.72, 200),
        ("NM-12350", "12/3 NM-B w/ ground", "wire", "ft", 420, 1.05, 100),
        ("NM-6250", "6/2 NM-B w/ ground", "wire", "ft", 180, 2.40, 50),
        ("NM-6350", "6/3 NM-B w/ ground", "wire", "ft", 140, 3.15, 40),
        ("SER-40", "4/0-4/0-2/0 aluminum SER", "wire", "ft", 90, 4.80, 25),
        ("THHN-12", "THHN 12 AWG stranded copper", "wire", "ft", 600, 0.38, 150),
        ("BRK-20", "20A 1-pole breaker (QO/BR)", "breakers", "ea", 48, 9.40, 12),
        ("BRK-15", "15A 1-pole breaker", "breakers", "ea", 52, 8.90, 12),
        ("BRK-50-2", "50A 2-pole breaker", "breakers", "ea", 14, 22.00, 4),
        ("BRK-60-2", "60A 2-pole breaker", "breakers", "ea", 10, 28.50, 3),
        ("PNL-200", "200A 40-space main breaker panel", "panels", "ea", 3, 186.00, 1),
        ("SURGE-WH", "Whole-house surge protector Type 2", "devices", "ea", 6, 92.00, 2),
        ("GFCI-20", "20A GFCI receptacle, white", "devices", "ea", 36, 18.50, 10),
        ("REC-15", "15A duplex receptacle, white", "devices", "ea", 120, 1.35, 40),
        ("SW-3WAY", "3-way switch, white", "devices", "ea", 40, 2.10, 12),
        ("LED-6CAN", "6\" LED remodel can, 2700K", "fixtures", "ea", 28, 14.80, 8),
        ("LED-WRAP", "4-ft LED wraparound, 4000K", "fixtures", "ea", 16, 42.00, 4),
        ("EMT-34", '3/4" EMT conduit', "conduit", "stick", 64, 6.80, 16),
        ("EMT-CONN34", '3/4" EMT set-screw connector', "fittings", "ea", 80, 0.55, 20),
        ("WBOX-1G", "1-gang old-work box", "fittings", "ea", 55, 1.15, 15),
        ("EVSE-N50", "NEMA 14-50 receptacle, industrial", "devices", "ea", 8, 28.00, 2),
        ("MC-122", "12/2 MC cable", "wire", "ft", 300, 1.22, 80),
    ]
    for item in inventory:
        conn.execute(
            "INSERT INTO inventory (sku, name, category, unit, qty_on_hand, unit_cost, reorder_level) VALUES (?,?,?,?,?,?,?)",
            item,
        )

    # Quotes
    quotes = [
        # 1 Patricia panel — accepted
        ("Q-1001", 1, 1, "accepted", "Replace 100A fuse box with 200A Square D. Permit included in labor.", 0.06625, ago(20), day_offset(10)),
        # 2 Maplewood Vet lighting — sent, waiting
        ("Q-1002", 2, 2, "sent", "Swap fluorescent wraps in treatment and waiting rooms. After 7pm.", 0.06625, ago(6), day_offset(21)),
        # 3 Ortiz EV — accepted, converted
        ("Q-1003", 3, 3, "accepted", "NEMA 14-50 on dedicated 50A. Homeline panel has space. Load calc attached.", 0.06625, ago(12), day_offset(5)),
        # 4 Church — draft
        ("Q-1004", 5, 7, "draft", "Sanctuary lights flicker when organ is on. Suspect shared neutral / loose in attic junction.", 0.06625, ago(2), day_offset(28)),
        # 5 Moretti addition — accepted
        ("Q-1005", 8, 10, "accepted", "Rough-in addition: 8 recs, 4 cans, 3-way stair, smoke. Trim quoted separately.", 0.06625, ago(9), day_offset(14)),
        # 6 Harrington declined
        ("Q-1006", 4, 5, "declined", "They went with in-house super for the outlet adds. Keep relationship.", 0.06625, ago(28), day_offset(-10)),
        # 7 Lakeside — accepted converted
        ("Q-1007", 7, 9, "accepted", "Parking lot poles and clubhouse wraps. Night work.", 0.06625, ago(25), day_offset(-5)),
    ]
    for q in quotes:
        conn.execute(
            """INSERT INTO quotes (number, customer_id, address_id, status, notes, tax_rate, created_at, valid_until)
               VALUES (?,?,?,?,?,?,?,?)""",
            q,
        )

    q_items = [
        # Q-1001 panel
        (1, "labor", "Pull permit, disconnect, hang 200A 40-space panel, land feeders", 8, "hr", 125, None),
        (1, "material", "200A 40-space main breaker panel", 1, "ea", 186, 11),
        (1, "material", "4/0-4/0-2/0 aluminum SER (service)", 18, "ft", 4.80, 5),
        (1, "labor", "Label, test, inspection walkthrough", 2, "hr", 125, None),
        (1, "material", "Whole-house surge protector Type 2", 1, "ea", 92, 12),
        # Q-1002 vet
        (2, "labor", "After-hours lighting retrofit — 2 techs", 6, "hr", 125, None),
        (2, "material", "4-ft LED wraparound, 4000K", 14, "ea", 42, 17),
        (2, "labor", "Dispose old ballasts (PCB-free) and punch list", 1, "hr", 125, None),
        # Q-1003 EV
        (3, "labor", "Run 6/3, land 50A 2-pole, install 14-50, test", 5, "hr", 125, None),
        (3, "material", "6/3 NM-B w/ ground", 45, "ft", 3.15, 4),
        (3, "material", "50A 2-pole breaker", 1, "ea", 22, 9),
        (3, "material", "NEMA 14-50 receptacle, industrial", 1, "ea", 28, 21),
        # Q-1004 church draft
        (4, "labor", "Troubleshoot sanctuary lighting / shared neutral", 3, "hr", 125, None),
        (4, "labor", "Repair / re-land junctions as found (est.)", 2, "hr", 125, None),
        # Q-1005 addition
        (5, "labor", "Rough-in addition (2 techs)", 10, "hr", 125, None),
        (5, "material", "12/2 NM-B w/ ground", 250, "ft", 0.72, 1),
        (5, "material", "12/3 NM-B w/ ground", 80, "ft", 1.05, 2),
        (5, "material", "1-gang old-work box", 12, "ea", 1.15, 20),
        (5, "material", '6" LED remodel can, 2700K', 4, "ea", 14.80, 16),
        # Q-1006 declined
        (6, "labor", "Add 6 recs in unit 3B", 4, "hr", 125, None),
        (6, "material", "15A duplex receptacle, white", 6, "ea", 1.35, 14),
        # Q-1007 lakeside
        (7, "labor", "Night work — clubhouse wraps + 4 parking poles", 8, "hr", 135, None),
        (7, "material", "4-ft LED wraparound, 4000K", 8, "ea", 42, 17),
    ]
    for it in q_items:
        conn.execute(
            """INSERT INTO quote_items (quote_id, kind, description, qty, unit, unit_price, inventory_id)
               VALUES (?,?,?,?,?,?,?)""",
            it,
        )

    # Jobs — ids will be 1..5
    # J-2001 Ryan Cho complete billed (last week Monday-ish)
    # J-2002 Ortiz EV in progress (today / this week)
    # J-2003 Brennan panel scheduled Thu
    # J-2004 Moretti rough-in scheduled Fri
    # J-2005 Lakeside complete billed overdue
    jobs = [
        (
            "J-2001", 6, 8, None, "service_call", "billed", 3,
            day_offset(-5), "09:00", "11:00",
            "Kitchen cans flickering. Check dimmer, cans, and homerun.",
            "Found loose wirenut in first can. Replaced dimmer.",
            ago(8), ago(5, 11),
        ),
        (
            "J-2002", 3, 3, 3, "ev_charger", "in_progress", 2,
            today.isoformat(), "08:00", "13:00",
            "Install NEMA 14-50 for Tesla. Dedicated 50A from Homeline. Load calc on file.",
            "Pipe run done yesterday. Landing breaker and 14-50 today.",
            ago(4), None,
        ),
        (
            "J-2003", 1, 1, 1, "panel_upgrade", "scheduled", 2,
            day_offset(1), "08:00", "16:00",
            "100A fuse box to 200A Square D. Permit pulled. Utility disconnect 8am.",
            "Call JCP&L morning-of. Patricia will be home.",
            ago(7), None,
        ),
        (
            "J-2004", 8, 10, 5, "new_construction", "scheduled", 3,
            day_offset(2), "07:30", "15:30",
            "Rough-in garage addition: 8 recs, 4 cans, 3-way, smoke. Coordinate with Brennan Builders.",
            "GC wants us in before insulation Friday.",
            ago(6), None,
        ),
        (
            "J-2005", 7, 9, 7, "lighting", "billed", 4,
            day_offset(-18), "18:00", "23:00",
            "Clubhouse LED wraps and parking lot pole heads.",
            "Two poles needed extra whip. Board signed ticket.",
            ago(22), ago(18, 23),
        ),
        (
            "J-2006", 4, 4, None, "troubleshooting", "complete", 4,
            day_offset(-40), "10:00", "13:00",
            "Building A hallway lights dead — 3-way. Find open.",
            "Open traveler in box 2. Restored. Invoice outstanding.",
            ago(45), ago(40, 13),
        ),
    ]
    # Wait I said 2006 as next job no. I have J-2001..2005 in seed then a 6th as 2006.
    # Settings next_job_no was 2006. Let me fix: 6 jobs = 2001-2006, next should be 2007.
    # I'll update settings after seed.

    for j in jobs:
        conn.execute(
            """INSERT INTO jobs (
                 number, customer_id, address_id, quote_id, job_type, status, tech_id,
                 scheduled_date, scheduled_start, scheduled_end, scope, notes, created_at, completed_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            j,
        )

    # Extra job this week: service call tomorrow morning for Harrington B
    conn.execute(
        """INSERT INTO jobs (
             number, customer_id, address_id, quote_id, job_type, status, tech_id,
             scheduled_date, scheduled_start, scheduled_end, scope, notes, created_at, completed_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "J-2007", 4, 5, None, "service_call", "scheduled", 4,
            day_offset(1), "16:00", "18:00",
            "Building B — unit 2C no power to dishwasher. Check circuit / GFCI.",
            "Super will meet Sofia at the lockbox.",
            ago(1), None,
        ),
    )

    job_mats = [
        (1, 16, '6" LED remodel can, 2700K', 1, "ea", 14.80),
        (1, 14, "15A duplex receptacle, white", 1, "ea", 1.35),
        (2, 4, "6/3 NM-B w/ ground", 48, "ft", 3.15),
        (2, 9, "50A 2-pole breaker", 1, "ea", 22.00),
        (5, 17, "4-ft LED wraparound, 4000K", 8, "ea", 42.00),
        (6, 7, "20A 1-pole breaker (QO/BR)", 1, "ea", 9.40),
    ]
    for m in job_mats:
        conn.execute(
            """INSERT INTO job_materials (job_id, inventory_id, description, qty, unit, unit_cost)
               VALUES (?,?,?,?,?,?)""",
            m,
        )
        # decrement stock for historical pulls
        conn.execute(
            "UPDATE inventory SET qty_on_hand = qty_on_hand - ? WHERE id = ?",
            (m[3], m[1]),
        )

    job_notes = [
        (1, "Homeowner on site. Dimmer was overheating — swapped to LED-rated.", ago(5, 11)),
        (2, "Ran 6/3 through basement joists. Need to land 14-50 and breaker today.", ago(1, 16)),
        (3, "Permit # WFD-26-4418 approved. Utility window 8:00–9:30.", ago(2, 9)),
        (5, "Board walkthrough complete. Left extra wraps in clubhouse closet.", ago(18, 23)),
        (6, "Chris Harrington asked to bill the building entity, not the tenant.", ago(40, 14)),
    ]
    for n in job_notes:
        conn.execute(
            "INSERT INTO job_notes (job_id, body, created_at) VALUES (?,?,?)",
            n,
        )

    # Invoices
    invoices = [
        ("INV-3001", 6, 1, 8, "paid", 0.06625, ago(5, 15), (today - timedelta(days=5) + timedelta(days=15)).isoformat(), "Kitchen lighting repair."),
        ("INV-3002", 7, 5, 9, "unpaid", 0.06625, ago(17, 10), (today - timedelta(days=2)).isoformat(), "Clubhouse and parking lighting. Net 15 — now overdue."),
        ("INV-3003", 4, 6, 4, "unpaid", 0.06625, ago(38, 16), (today - timedelta(days=23)).isoformat(), "Building A hallway 3-way repair."),
        ("INV-3004", 3, 2, 3, "unpaid", 0.06625, today.isoformat() + "T12:00:00", (today + timedelta(days=15)).isoformat(), "Progress bill for EV circuit — materials + labor to date."),
    ]
    for inv in invoices:
        conn.execute(
            """INSERT INTO invoices (number, customer_id, job_id, address_id, status, tax_rate, issued_at, due_date, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            inv,
        )

    inv_items = [
        (1, "Service call — diagnose flickering kitchen cans", 1, 125),
        (1, "Replace LED-rated dimmer and re-land can", 1, 95),
        (1, '6" LED remodel can, 2700K', 1, 22),
        (2, "Night work — clubhouse wraps + parking poles (8 hr)", 8, 135),
        (2, "4-ft LED wraparound, 4000K", 8, 62),
        (3, "Troubleshoot and repair hallway 3-way", 3, 125),
        (3, "20A 1-pole breaker", 1, 14),
        (4, "EV charger circuit labor (5 hr)", 5, 125),
        (4, "6/3 NM-B w/ ground (48 ft)", 48, 4.50),
        (4, "50A 2-pole breaker", 1, 32),
        (4, "NEMA 14-50 receptacle, industrial", 1, 42),
    ]
    for it in inv_items:
        conn.execute(
            "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
            it,
        )

    conn.execute(
        "INSERT INTO payments (invoice_id, amount, method, paid_at, reference) VALUES (?,?,?,?,?)",
        (1, 258.00, "card", ago(4, 10), "Visa ••4412"),
    )

    # next numbers after seed
    conn.execute(
        "UPDATE settings SET next_quote_no = 1008, next_job_no = 2008, next_invoice_no = 3005 WHERE id = 1"
    )
    conn.commit()
