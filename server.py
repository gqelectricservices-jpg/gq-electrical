#!/usr/bin/env python3
"""GQ Electrical Services — back-office HTTP server (stdlib + sqlite3)."""
from __future__ import annotations

import json
import os
import mimetypes
import re
import sqlite3
import traceback
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
TZ = ZoneInfo("America/New_York")
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import db as store
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/jpeg", ".jpeg")

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "3000"))

CONN = store.get_conn()
store.init_db(CONN)

JOB_TYPES = [
    "service_call",
    "panel_upgrade",
    "lighting",
    "ev_charger",
    "troubleshooting",
    "new_construction",
    "other",
]
JOB_STATUSES = ["scheduled", "in_progress", "complete", "billed"]
QUOTE_STATUSES = ["draft", "sent", "accepted", "declined"]
PAY_METHODS = ["check", "cash", "card", "ach", "other"]


def now_iso() -> str:
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")


def today() -> date:
    return datetime.now(TZ).date()


def money(n) -> float:
    try:
        return round(float(n or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def line_total(item) -> float:
    return money(item.get("qty", 1) * item.get("unit_price", 0))


def quote_totals(conn, quote_id: int, tax_rate=None):
    items = conn.execute(
        "SELECT * FROM quote_items WHERE quote_id = ? ORDER BY id", (quote_id,)
    ).fetchall()
    sub = sum(line_total(i) for i in items)
    if tax_rate is None:
        q = conn.execute("SELECT tax_rate FROM quotes WHERE id = ?", (quote_id,)).fetchone()
        tax_rate = q["tax_rate"] if q else 0
    tax = money(sub * tax_rate)
    return {"subtotal": money(sub), "tax": tax, "total": money(sub + tax), "items": items}


def invoice_totals(conn, invoice_id: int):
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    items = conn.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (invoice_id,)
    ).fetchall()
    pays = conn.execute(
        "SELECT * FROM payments WHERE invoice_id = ? ORDER BY paid_at", (invoice_id,)
    ).fetchall()
    sub = sum(line_total(i) for i in items)
    tax = money(sub * (inv["tax_rate"] if inv else 0))
    total = money(sub + tax)
    paid = money(sum(p["amount"] for p in pays))
    balance = money(total - paid)
    status = inv["status"] if inv else "unpaid"
    due = inv["due_date"] if inv else None
    if balance <= 0 and total > 0:
        status = "paid"
    elif paid > 0 and balance > 0:
        status = "partial"
    elif balance > 0 and due and due < today().isoformat():
        status = "overdue"
    else:
        status = "unpaid" if balance > 0 else "paid"
    return {
        "subtotal": money(sub),
        "tax": tax,
        "total": total,
        "paid": paid,
        "balance": balance,
        "status": status,
        "items": items,
        "payments": pays,
    }


def hydrate_invoice(conn, inv):
    t = invoice_totals(conn, inv["id"])
    inv = dict(inv)
    inv.update({k: t[k] for k in ("subtotal", "tax", "total", "paid", "balance", "status")})
    inv["items"] = t["items"]
    inv["payments"] = t["payments"]
    cust = conn.execute("SELECT * FROM customers WHERE id = ?", (inv["customer_id"],)).fetchone()
    inv["customer"] = cust
    if inv.get("address_id"):
        inv["address"] = conn.execute(
            "SELECT * FROM addresses WHERE id = ?", (inv["address_id"],)
        ).fetchone()
    if inv.get("job_id"):
        inv["job"] = conn.execute("SELECT * FROM jobs WHERE id = ?", (inv["job_id"],)).fetchone()
    return inv


def hydrate_quote(conn, q):
    q = dict(q)
    t = quote_totals(conn, q["id"], q["tax_rate"])
    q.update({k: t[k] for k in ("subtotal", "tax", "total")})
    q["items"] = t["items"]
    q["customer"] = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (q["customer_id"],)
    ).fetchone()
    if q.get("address_id"):
        q["address"] = conn.execute(
            "SELECT * FROM addresses WHERE id = ?", (q["address_id"],)
        ).fetchone()
    return q


def hydrate_job(conn, j):
    j = dict(j)
    j["customer"] = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (j["customer_id"],)
    ).fetchone()
    if j.get("address_id"):
        j["address"] = conn.execute(
            "SELECT * FROM addresses WHERE id = ?", (j["address_id"],)
        ).fetchone()
    if j.get("tech_id"):
        j["tech"] = conn.execute("SELECT * FROM team WHERE id = ?", (j["tech_id"],)).fetchone()
    if j.get("quote_id"):
        j["quote"] = conn.execute(
            "SELECT id, number, status FROM quotes WHERE id = ?", (j["quote_id"],)
        ).fetchone()
    j["materials"] = conn.execute(
        "SELECT * FROM job_materials WHERE job_id = ? ORDER BY id", (j["id"],)
    ).fetchall()
    j["job_notes"] = conn.execute(
        "SELECT * FROM job_notes WHERE job_id = ? ORDER BY id DESC", (j["id"],)
    ).fetchall()
    inv = conn.execute("SELECT * FROM invoices WHERE job_id = ?", (j["id"],)).fetchone()
    j["invoice"] = {"id": inv["id"], "number": inv["number"]} if inv else None
    return j


def hydrate_customer(conn, c):
    c = dict(c)
    c["addresses"] = conn.execute(
        "SELECT * FROM addresses WHERE customer_id = ? ORDER BY id", (c["id"],)
    ).fetchall()
    c["quotes"] = [
        hydrate_quote(conn, q)
        for q in conn.execute(
            "SELECT * FROM quotes WHERE customer_id = ? ORDER BY id DESC", (c["id"],)
        ).fetchall()
    ]
    c["jobs"] = [
        hydrate_job(conn, j)
        for j in conn.execute(
            "SELECT * FROM jobs WHERE customer_id = ? ORDER BY scheduled_date DESC, id DESC",
            (c["id"],),
        ).fetchall()
    ]
    c["invoices"] = [
        hydrate_invoice(conn, i)
        for i in conn.execute(
            "SELECT * FROM invoices WHERE customer_id = ? ORDER BY issued_at DESC", (c["id"],)
        ).fetchall()
    ]
    return c



def phone_digits(p) -> str:
    d = re.sub(r"\D", "", str(p or ""))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d[-10:] if len(d) >= 10 else d


def names_match(a, b) -> bool:
    na = " ".join((a or "").lower().replace("&", " ").split())
    nb = " ".join((b or "").lower().replace("&", " ").split())
    if not na or not nb:
        return False
    if na == nb or nb in na or na in nb:
        return True
    pa, pb = na.split(), nb.split()
    if pa[-1] == pb[-1] and (pa[0] in nb or pb[0] in na):
        return True
    return False


def find_customer_by_phone(conn, phone):
    digits = phone_digits(phone)
    if not digits:
        return None
    for c in conn.execute("SELECT * FROM customers").fetchall():
        if phone_digits(c["phone"]) == digits:
            return c
    return None


def find_customer_by_portal_code(conn, code):
    raw = re.sub(r"\s+", "", str(code or "")).upper()
    if not raw:
        return None
    return conn.execute(
        "SELECT * FROM customers WHERE REPLACE(UPPER(COALESCE(portal_code,'')), ' ', '') = ?",
        (raw,),
    ).fetchone()


def hydrate_request(conn, r):
    r = dict(r)
    if r.get("customer_id"):
        r["customer"] = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (r["customer_id"],)
        ).fetchone()
    else:
        r["customer"] = None
    return r


# Fallbacks when settings fields are empty — keep public site usable.
PUBLIC_DEFAULTS = {
    "company_name": "GQ Electrical Services",
    "phone": "+1 (689) 500-6543",
    "email": "Services@gqelectrical.com",
    "street": "2207 Plantation Lakes Cir",
    "city": "Sanford",
    "state": "FL",
    "zip": "32771",
    "service_area": "Seminole, Orange, Volusia, and Lake Counties — and surrounding Central Florida",
    "license_no": "ER13016834",
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


def _filled(val, key):
    if val is None:
        return PUBLIC_DEFAULTS.get(key)
    s = str(val).strip()
    return s if s else PUBLIC_DEFAULTS.get(key)


def public_company(conn):
    s = settings_row(conn) or {}
    loc = _filled(s.get("location_line"), "location_line")
    if not loc:
        city = _filled(s.get("city"), "city")
        state = _filled(s.get("state"), "state")
        loc = ", ".join(x for x in (city, "Florida" if state == "FL" else state) if x)
    return {
        "company_name": _filled(s.get("company_name"), "company_name"),
        "phone": _filled(s.get("phone"), "phone"),
        "email": _filled(s.get("email"), "email"),
        "street": _filled(s.get("street"), "street"),
        "city": _filled(s.get("city"), "city"),
        "state": _filled(s.get("state"), "state"),
        "zip": _filled(s.get("zip"), "zip"),
        "service_area": _filled(s.get("service_area"), "service_area"),
        "license_no": _filled(s.get("license_no"), "license_no"),
        "tagline": _filled(s.get("tagline"), "tagline"),
        "location_line": loc,
        "hero_headline": _filled(s.get("hero_headline"), "hero_headline"),
        "hero_subhead": _filled(s.get("hero_subhead"), "hero_subhead"),
        "about_blurb": _filled(s.get("about_blurb"), "about_blurb"),
        "invoice_footer": s.get("invoice_footer") or "",
    }


def portal_payload(conn, c):
    c = hydrate_customer(conn, c)
    jobs = [
        {
            "id": j["id"],
            "number": j["number"],
            "job_type": j["job_type"],
            "status": j["status"],
            "scheduled_date": j["scheduled_date"],
            "scheduled_start": j["scheduled_start"],
            "scheduled_end": j["scheduled_end"],
            "scope": j["scope"],
            "address": j.get("address"),
            "tech": {"name": j["tech"]["name"]} if j.get("tech") else None,
        }
        for j in c["jobs"]
    ]
    quotes = [
        {
            "id": q["id"],
            "number": q["number"],
            "status": q["status"],
            "created_at": q["created_at"],
            "valid_until": q["valid_until"],
            "subtotal": q["subtotal"],
            "tax": q["tax"],
            "total": q["total"],
            "notes": q["notes"],
            "items": q["items"],
            "address": q.get("address"),
        }
        for q in c["quotes"]
    ]
    invoices = [
        {
            "id": i["id"],
            "number": i["number"],
            "status": i["status"],
            "issued_at": i["issued_at"],
            "due_date": i["due_date"],
            "subtotal": i["subtotal"],
            "tax": i["tax"],
            "total": i["total"],
            "paid": i["paid"],
            "balance": i["balance"],
            "items": i["items"],
            "payments": [
                {
                    "amount": p["amount"],
                    "method": p["method"],
                    "paid_at": p["paid_at"],
                    "reference": p["reference"],
                }
                for p in (i.get("payments") or [])
            ],
            "address": i.get("address"),
            "job": {"id": i["job"]["id"], "number": i["job"]["number"]} if i.get("job") else None,
        }
        for i in c["invoices"]
    ]
    return {
        "customer": {
            "id": c["id"],
            "name": c["name"],
            "kind": c["kind"],
            "phone": c["phone"],
            "email": c["email"],
            "portal_code": c.get("portal_code"),
            "addresses": c["addresses"],
        },
        "quotes": quotes,
        "jobs": jobs,
        "invoices": invoices,
    }


def public_invoice_view(conn, inv):
    inv = hydrate_invoice(conn, inv)
    return {
        "id": inv["id"],
        "number": inv["number"],
        "status": inv["status"],
        "issued_at": inv["issued_at"],
        "due_date": inv["due_date"],
        "subtotal": inv["subtotal"],
        "tax": inv["tax"],
        "total": inv["total"],
        "paid": inv["paid"],
        "balance": inv["balance"],
        "notes": inv["notes"],
        "items": inv["items"],
        "payments": [
            {
                "amount": p["amount"],
                "method": p["method"],
                "paid_at": p["paid_at"],
                "reference": p["reference"],
            }
            for p in (inv.get("payments") or [])
        ],
        "customer": {
            "name": inv["customer"]["name"] if inv.get("customer") else None,
            "id": inv["customer_id"],
        },
        "address": inv.get("address"),
        "company": public_company(conn),
    }


def brand_card(num: str) -> str:
    d = re.sub(r"\D", "", str(num or ""))
    if len(d) < 13 or len(d) > 19:
        return ""
    if d.startswith("4"):
        brand = "Visa"
    elif d[:2] in {str(n) for n in range(51, 56)} or d.startswith("2"):
        brand = "Mastercard"
    elif d.startswith("34") or d.startswith("37"):
        brand = "American Express"
    elif d.startswith("6"):
        brand = "Discover"
    else:
        brand = "Card"
    return f"{brand} ••{d[-4:]}"


def settings_row(conn):
    return conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()


def read_json(handler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    if n == 0:
        return {}
    raw = handler.rfile.read(n)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "GQElectrical/1.0"

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            data = json.dumps(body, default=str).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _err(self, code, msg):
        self._send(code, {"error": msg})

    def do_GET(self):
        try:
            self._dispatch("GET")
        except Exception as e:
            traceback.print_exc()
            self._err(500, str(e))

    def do_POST(self):
        try:
            self._dispatch("POST")
        except Exception as e:
            traceback.print_exc()
            self._err(500, str(e))

    def do_PUT(self):
        try:
            self._dispatch("PUT")
        except Exception as e:
            traceback.print_exc()
            self._err(500, str(e))

    def do_DELETE(self):
        try:
            self._dispatch("DELETE")
        except Exception as e:
            traceback.print_exc()
            self._err(500, str(e))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET,POST,PUT,DELETE,OPTIONS")
        self.end_headers()

    def _dispatch(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        conn = CONN

        if not path.startswith("/api/"):
            return self._static(path)

        parts = [p for p in path.split("/") if p]
        # parts[0] == 'api'
        resource = parts[1] if len(parts) > 1 else ""
        ident = parts[2] if len(parts) > 2 else None
        sub = parts[3] if len(parts) > 3 else None
        subid = parts[4] if len(parts) > 4 else None

        if resource == "health":
            return self._send(200, {"ok": True, "company": "GQ Electrical Services"})

        if resource == "dashboard" and method == "GET":
            return self._send(200, self._dashboard(conn))

        if resource == "settings":
            if method == "GET":
                return self._send(200, settings_row(conn))
            if method == "PUT":
                body = read_json(self)
                fields = [
                    "company_name",
                    "license_no",
                    "phone",
                    "email",
                    "street",
                    "city",
                    "state",
                    "zip",
                    "service_area",
                    "default_labor_rate",
                    "tax_rate",
                    "invoice_footer",
                    "tagline",
                    "location_line",
                    "hero_headline",
                    "hero_subhead",
                    "about_blurb",
                ]
                sets, vals = [], []
                for f in fields:
                    if f in body:
                        sets.append(f"{f} = ?")
                        vals.append(body[f])
                if sets:
                    conn.execute(f"UPDATE settings SET {', '.join(sets)} WHERE id = 1", vals)
                    conn.commit()
                return self._send(200, settings_row(conn))

        if resource == "team":
            if method == "GET" and not ident:
                rows = conn.execute(
                    "SELECT * FROM team ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'technician' THEN 1 ELSE 2 END, name"
                ).fetchall()
                return self._send(200, rows)
            if method == "POST" and not ident:
                body = read_json(self)
                cur = conn.execute(
                    "INSERT INTO team (name, role, phone, email, color, active) VALUES (?,?,?,?,?,?)",
                    (
                        body.get("name") or "Unnamed",
                        body.get("role") or "technician",
                        body.get("phone"),
                        body.get("email"),
                        body.get("color") or "#1c3a5f",
                        1 if body.get("active", True) else 0,
                    ),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM team WHERE id = ?", (cur.lastrowid,)).fetchone()
                return self._send(201, row)
            if ident and method == "PUT":
                body = read_json(self)
                conn.execute(
                    "UPDATE team SET name=?, role=?, phone=?, email=?, color=?, active=? WHERE id=?",
                    (
                        body.get("name"),
                        body.get("role"),
                        body.get("phone"),
                        body.get("email"),
                        body.get("color"),
                        1 if body.get("active", True) else 0,
                        ident,
                    ),
                )
                conn.commit()
                return self._send(200, conn.execute("SELECT * FROM team WHERE id=?", (ident,)).fetchone())
            if ident and method == "DELETE":
                row = conn.execute("SELECT * FROM team WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Team member not found")
                try:
                    self._cascade_delete_team(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete team member: {e}")
                return self._send(200, {"ok": True, "deleted": "team", "id": int(ident)})

        if resource == "inventory":
            if method == "GET" and not ident:
                rows = conn.execute(
                    "SELECT * FROM inventory ORDER BY category, name"
                ).fetchall()
                for r in rows:
                    r["low"] = r["qty_on_hand"] <= r["reorder_level"]
                return self._send(200, rows)
            if method == "POST" and not ident:
                body = read_json(self)
                cur = conn.execute(
                    """INSERT INTO inventory (sku, name, category, unit, qty_on_hand, unit_cost, reorder_level)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        body.get("sku"),
                        body.get("name") or "Item",
                        body.get("category") or "other",
                        body.get("unit") or "ea",
                        money(body.get("qty_on_hand")),
                        money(body.get("unit_cost")),
                        money(body.get("reorder_level")),
                    ),
                )
                conn.commit()
                return self._send(201, conn.execute("SELECT * FROM inventory WHERE id=?", (cur.lastrowid,)).fetchone())
            if ident and method == "PUT":
                body = read_json(self)
                conn.execute(
                    """UPDATE inventory SET sku=?, name=?, category=?, unit=?, qty_on_hand=?, unit_cost=?, reorder_level=?
                       WHERE id=?""",
                    (
                        body.get("sku"),
                        body.get("name"),
                        body.get("category"),
                        body.get("unit"),
                        money(body.get("qty_on_hand")),
                        money(body.get("unit_cost")),
                        money(body.get("reorder_level")),
                        ident,
                    ),
                )
                conn.commit()
                return self._send(200, conn.execute("SELECT * FROM inventory WHERE id=?", (ident,)).fetchone())
            if ident and method == "DELETE":
                row = conn.execute("SELECT * FROM inventory WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Inventory item not found")
                try:
                    self._cascade_delete_inventory(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete inventory item: {e}")
                return self._send(200, {"ok": True, "deleted": "inventory", "id": int(ident)})

        if resource == "customers":
            if method == "GET" and not ident:
                q = (qs.get("q") or [""])[0].strip().lower()
                rows = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
                out = []
                for c in rows:
                    addrs = conn.execute(
                        "SELECT * FROM addresses WHERE customer_id = ?", (c["id"],)
                    ).fetchall()
                    c = dict(c)
                    c["addresses"] = addrs
                    blob = " ".join(
                        [
                            c["name"] or "",
                            c["phone"] or "",
                            c["email"] or "",
                            " ".join(f"{a['street']} {a['city']}" for a in addrs),
                        ]
                    ).lower()
                    if q and q not in blob:
                        continue
                    out.append(c)
                return self._send(200, out)
            if method == "POST" and not ident:
                body = read_json(self)
                cur = conn.execute(
                    "INSERT INTO customers (name, kind, phone, email, notes, source, portal_code, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        body.get("name") or "New customer",
                        body.get("kind") or "person",
                        body.get("phone"),
                        body.get("email"),
                        body.get("notes"),
                        body.get("source") or "shop",
                        body.get("portal_code") or store.new_portal_code(conn),
                        now_iso(),
                    ),
                )
                cid = cur.lastrowid
                addr = body.get("address") or {}
                if addr.get("street"):
                    conn.execute(
                        "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
                        (
                            cid,
                            addr.get("label") or "Service",
                            addr.get("street"),
                            addr.get("city") or "",
                            addr.get("state") or "FL",
                            addr.get("zip"),
                        ),
                    )
                conn.commit()
                return self._send(201, hydrate_customer(conn, conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()))
            if ident and method == "GET" and not sub:
                row = conn.execute("SELECT * FROM customers WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Customer not found")
                return self._send(200, hydrate_customer(conn, row))
            if ident and method == "PUT" and not sub:
                body = read_json(self)
                conn.execute(
                    "UPDATE customers SET name=?, kind=?, phone=?, email=?, notes=? WHERE id=?",
                    (
                        body.get("name"),
                        body.get("kind"),
                        body.get("phone"),
                        body.get("email"),
                        body.get("notes"),
                        ident,
                    ),
                )
                conn.commit()
                return self._send(200, hydrate_customer(conn, conn.execute("SELECT * FROM customers WHERE id=?", (ident,)).fetchone()))
            if ident and method == "DELETE" and not sub:
                row = conn.execute("SELECT * FROM customers WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Customer not found")
                try:
                    self._cascade_delete_customer(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete customer: {e}")
                return self._send(200, {"ok": True, "deleted": "customer", "id": int(ident), "name": row["name"]})
            if ident and sub == "addresses" and method == "POST":
                body = read_json(self)
                cur = conn.execute(
                    "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
                    (
                        ident,
                        body.get("label") or "Service",
                        body.get("street") or "",
                        body.get("city") or "",
                        body.get("state") or "FL",
                        body.get("zip"),
                    ),
                )
                conn.commit()
                return self._send(201, conn.execute("SELECT * FROM addresses WHERE id=?", (cur.lastrowid,)).fetchone())

        if resource == "quotes":
            if method == "GET" and not ident:
                status = (qs.get("status") or [None])[0]
                sql = "SELECT * FROM quotes"
                args = []
                if status:
                    sql += " WHERE status = ?"
                    args.append(status)
                sql += " ORDER BY id DESC"
                rows = [hydrate_quote(conn, q) for q in conn.execute(sql, args).fetchall()]
                return self._send(200, rows)
            if method == "POST" and not ident:
                body = read_json(self)
                s = settings_row(conn)
                num = store.next_number(conn, "quote")
                cur = conn.execute(
                    """INSERT INTO quotes (number, customer_id, address_id, status, notes, tax_rate, created_at, valid_until)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        num,
                        body["customer_id"],
                        body.get("address_id"),
                        body.get("status") or "draft",
                        body.get("notes"),
                        float(body.get("tax_rate", s["tax_rate"])),
                        now_iso(),
                        body.get("valid_until"),
                    ),
                )
                qid = cur.lastrowid
                self._replace_quote_items(conn, qid, body.get("items") or [])
                conn.commit()
                return self._send(201, hydrate_quote(conn, conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()))
            if ident and method == "GET" and not sub:
                row = conn.execute("SELECT * FROM quotes WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Quote not found")
                return self._send(200, hydrate_quote(conn, row))
            if ident and method == "PUT" and not sub:
                body = read_json(self)
                row = conn.execute("SELECT * FROM quotes WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Quote not found")
                conn.execute(
                    """UPDATE quotes SET customer_id=?, address_id=?, status=?, notes=?, tax_rate=?, valid_until=?
                       WHERE id=?""",
                    (
                        body.get("customer_id", row["customer_id"]),
                        body.get("address_id", row["address_id"]),
                        body.get("status", row["status"]),
                        body.get("notes", row["notes"]),
                        float(body.get("tax_rate", row["tax_rate"])),
                        body.get("valid_until", row["valid_until"]),
                        ident,
                    ),
                )
                if "items" in body:
                    conn.execute("DELETE FROM quote_items WHERE quote_id=?", (ident,))
                    self._replace_quote_items(conn, ident, body["items"])
                conn.commit()
                return self._send(200, hydrate_quote(conn, conn.execute("SELECT * FROM quotes WHERE id=?", (ident,)).fetchone()))
            if ident and method == "DELETE" and not sub:
                row = conn.execute("SELECT * FROM quotes WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Quote not found")
                try:
                    self._cascade_delete_quote(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete quote: {e}")
                return self._send(200, {"ok": True, "deleted": "quote", "id": int(ident)})
            if ident and sub == "convert" and method == "POST":
                return self._convert_quote(conn, ident)

        if resource == "jobs":
            if method == "GET" and not ident:
                status = (qs.get("status") or [None])[0]
                week = (qs.get("week") or [None])[0]
                sql = "SELECT * FROM jobs WHERE 1=1"
                args = []
                if status:
                    sql += " AND status = ?"
                    args.append(status)
                if week:
                    start = date.fromisoformat(week)
                    start = start - timedelta(days=start.weekday())
                    end = start + timedelta(days=6)
                    sql += " AND scheduled_date BETWEEN ? AND ?"
                    args.extend([start.isoformat(), end.isoformat()])
                sql += " ORDER BY scheduled_date, scheduled_start, id"
                rows = [hydrate_job(conn, j) for j in conn.execute(sql, args).fetchall()]
                return self._send(200, rows)
            if method == "POST" and not ident:
                body = read_json(self)
                num = store.next_number(conn, "job")
                cur = conn.execute(
                    """INSERT INTO jobs (
                         number, customer_id, address_id, quote_id, job_type, status, tech_id,
                         scheduled_date, scheduled_start, scheduled_end, scope, notes, created_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        num,
                        body["customer_id"],
                        body.get("address_id"),
                        body.get("quote_id"),
                        body.get("job_type") or "service_call",
                        body.get("status") or "scheduled",
                        body.get("tech_id"),
                        body.get("scheduled_date"),
                        body.get("scheduled_start"),
                        body.get("scheduled_end"),
                        body.get("scope"),
                        body.get("notes"),
                        now_iso(),
                    ),
                )
                conn.commit()
                jid = cur.lastrowid
                return self._send(201, hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()))
            if ident and method == "GET" and not sub:
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Job not found")
                return self._send(200, hydrate_job(conn, row))
            if ident and method == "PUT" and not sub:
                body = read_json(self)
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Job not found")
                new_status = body.get("status", row["status"])
                completed = row["completed_at"]
                if new_status == "complete" and not completed:
                    completed = now_iso()
                if new_status in ("scheduled", "in_progress"):
                    completed = None
                conn.execute(
                    """UPDATE jobs SET customer_id=?, address_id=?, job_type=?, status=?, tech_id=?,
                       scheduled_date=?, scheduled_start=?, scheduled_end=?, scope=?, notes=?, completed_at=?
                       WHERE id=?""",
                    (
                        body.get("customer_id", row["customer_id"]),
                        body.get("address_id", row["address_id"]),
                        body.get("job_type", row["job_type"]),
                        new_status,
                        body.get("tech_id", row["tech_id"]),
                        body.get("scheduled_date", row["scheduled_date"]),
                        body.get("scheduled_start", row["scheduled_start"]),
                        body.get("scheduled_end", row["scheduled_end"]),
                        body.get("scope", row["scope"]),
                        body.get("notes", row["notes"]),
                        completed,
                        ident,
                    ),
                )
                conn.commit()
                return self._send(200, hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()))
            if ident and method == "DELETE" and not sub:
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Job not found")
                try:
                    self._cascade_delete_job(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete job: {e}")
                return self._send(200, {"ok": True, "deleted": "job", "id": int(ident)})
            if ident and sub == "materials" and method == "POST":
                body = read_json(self)
                inv_id = body.get("inventory_id")
                qty = money(body.get("qty") or 1)
                desc = body.get("description")
                unit = body.get("unit") or "ea"
                cost = money(body.get("unit_cost") or 0)
                if inv_id:
                    inv = conn.execute("SELECT * FROM inventory WHERE id=?", (inv_id,)).fetchone()
                    if not inv:
                        return self._err(404, "Inventory item not found")
                    desc = desc or inv["name"]
                    unit = inv["unit"]
                    cost = inv["unit_cost"]
                    conn.execute(
                        "UPDATE inventory SET qty_on_hand = qty_on_hand - ? WHERE id=?",
                        (qty, inv_id),
                    )
                cur = conn.execute(
                    """INSERT INTO job_materials (job_id, inventory_id, description, qty, unit, unit_cost)
                       VALUES (?,?,?,?,?,?)""",
                    (ident, inv_id, desc or "Material", qty, unit, cost),
                )
                conn.commit()
                return self._send(201, hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()))
            if ident and sub == "materials" and subid and method == "DELETE":
                mat = conn.execute(
                    "SELECT * FROM job_materials WHERE id=? AND job_id=?", (subid, ident)
                ).fetchone()
                if not mat:
                    return self._err(404, "Material not found")
                if mat["inventory_id"]:
                    conn.execute(
                        "UPDATE inventory SET qty_on_hand = qty_on_hand + ? WHERE id=?",
                        (mat["qty"], mat["inventory_id"]),
                    )
                conn.execute("DELETE FROM job_materials WHERE id=?", (subid,))
                conn.commit()
                return self._send(200, hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()))
            if ident and sub == "notes" and method == "POST":
                body = read_json(self)
                conn.execute(
                    "INSERT INTO job_notes (job_id, body, created_at) VALUES (?,?,?)",
                    (ident, body.get("body") or "", now_iso()),
                )
                conn.commit()
                return self._send(201, hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()))
            if ident and sub == "invoice" and method == "POST":
                return self._invoice_from_job(conn, ident)

        if resource == "schedule" and method == "GET":
            week = (qs.get("week") or [today().isoformat()])[0]
            start = date.fromisoformat(week)
            start = start - timedelta(days=start.weekday())
            days = [(start + timedelta(days=i)).isoformat() for i in range(7)]
            techs = conn.execute(
                "SELECT * FROM team WHERE role IN ('technician','owner') AND active=1 ORDER BY name"
            ).fetchall()
            jobs = [
                hydrate_job(conn, j)
                for j in conn.execute(
                    "SELECT * FROM jobs WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_start",
                    (days[0], days[-1]),
                ).fetchall()
            ]
            return self._send(200, {"week_start": days[0], "days": days, "technicians": techs, "jobs": jobs})

        if resource == "invoices":
            if method == "GET" and not ident:
                rows = [
                    hydrate_invoice(conn, i)
                    for i in conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
                ]
                status = (qs.get("status") or [None])[0]
                if status:
                    rows = [r for r in rows if r["status"] == status]
                return self._send(200, rows)
            if method == "POST" and not ident:
                body = read_json(self)
                if body.get("job_id"):
                    return self._invoice_from_job(conn, body["job_id"])
                s = settings_row(conn)
                num = store.next_number(conn, "invoice")
                issued = body.get("issued_at") or now_iso()
                due = body.get("due_date") or (today() + timedelta(days=15)).isoformat()
                cur = conn.execute(
                    """INSERT INTO invoices (number, customer_id, job_id, address_id, status, tax_rate, issued_at, due_date, notes)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        num,
                        body["customer_id"],
                        body.get("job_id"),
                        body.get("address_id"),
                        "unpaid",
                        float(body.get("tax_rate", s["tax_rate"])),
                        issued,
                        due,
                        body.get("notes"),
                    ),
                )
                iid = cur.lastrowid
                for it in body.get("items") or []:
                    conn.execute(
                        "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
                        (iid, it.get("description") or "Line", money(it.get("qty") or 1), money(it.get("unit_price"))),
                    )
                conn.commit()
                return self._send(201, hydrate_invoice(conn, conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()))
            if ident and method == "GET" and not sub:
                row = conn.execute("SELECT * FROM invoices WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Invoice not found")
                inv = hydrate_invoice(conn, row)
                inv["company"] = settings_row(conn)
                return self._send(200, inv)
            if ident and sub == "payments" and method == "POST":
                body = read_json(self)
                amt = money(body.get("amount"))
                if amt <= 0:
                    return self._err(400, "Amount must be greater than 0")
                conn.execute(
                    "INSERT INTO payments (invoice_id, amount, method, paid_at, reference) VALUES (?,?,?,?,?)",
                    (
                        ident,
                        amt,
                        body.get("method") if body.get("method") in PAY_METHODS else "other",
                        body.get("paid_at") or now_iso(),
                        body.get("reference"),
                    ),
                )
                conn.commit()
                inv = hydrate_invoice(conn, conn.execute("SELECT * FROM invoices WHERE id=?", (ident,)).fetchone())
                conn.execute("UPDATE invoices SET status=? WHERE id=?", (inv["status"] if inv["status"] != "overdue" else "unpaid", ident))
                # keep computed status in response
                conn.commit()
                return self._send(201, inv)
            if ident and method == "PUT" and not sub:
                body = read_json(self)
                row = conn.execute("SELECT * FROM invoices WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Invoice not found")
                conn.execute(
                    "UPDATE invoices SET notes=?, due_date=?, tax_rate=? WHERE id=?",
                    (
                        body.get("notes", row["notes"]),
                        body.get("due_date", row["due_date"]),
                        float(body.get("tax_rate", row["tax_rate"])),
                        ident,
                    ),
                )
                if "items" in body:
                    conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (ident,))
                    for it in body["items"]:
                        conn.execute(
                            "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
                            (ident, it.get("description") or "Line", money(it.get("qty") or 1), money(it.get("unit_price"))),
                        )
                conn.commit()
                return self._send(200, hydrate_invoice(conn, conn.execute("SELECT * FROM invoices WHERE id=?", (ident,)).fetchone()))
            if ident and method == "DELETE" and not sub:
                row = conn.execute("SELECT * FROM invoices WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Invoice not found")
                try:
                    self._cascade_delete_invoice(conn, ident)
                    conn.commit()
                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    return self._err(409, f"Cannot delete invoice: {e}")
                return self._send(200, {"ok": True, "deleted": "invoice", "id": int(ident)})

        if resource == "meta" and method == "GET":
            return self._send(
                200,
                {
                    "job_types": JOB_TYPES,
                    "job_statuses": JOB_STATUSES,
                    "quote_statuses": QUOTE_STATUSES,
                    "pay_methods": PAY_METHODS,
                    "inventory_categories": [
                        "wire",
                        "breakers",
                        "devices",
                        "fixtures",
                        "conduit",
                        "panels",
                        "fittings",
                        "other",
                    ],
                },
            )


        if resource == "public":
            return self._public(conn, method, ident, sub, subid)

        if resource == "requests":
            if method == "GET" and not ident:
                status = (qs.get("status") or [None])[0]
                sql = "SELECT * FROM web_requests"
                args = []
                if status:
                    sql += " WHERE status = ?"
                    args.append(status)
                sql += " ORDER BY CASE status WHEN 'new' THEN 0 WHEN 'contacted' THEN 1 ELSE 2 END, id DESC"
                rows = [hydrate_request(conn, r) for r in conn.execute(sql, args).fetchall()]
                return self._send(200, rows)
            if ident and method == "GET":
                row = conn.execute("SELECT * FROM web_requests WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Request not found")
                return self._send(200, hydrate_request(conn, row))
            if ident and method == "PUT":
                body = read_json(self)
                row = conn.execute("SELECT * FROM web_requests WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Request not found")
                status = body.get("status", row["status"])
                if status not in ("new", "contacted", "converted", "closed"):
                    return self._err(400, "Invalid status")
                conn.execute("UPDATE web_requests SET status=? WHERE id=?", (status, ident))
                conn.commit()
                return self._send(200, hydrate_request(conn, conn.execute("SELECT * FROM web_requests WHERE id=?", (ident,)).fetchone()))
            if ident and method == "DELETE":
                row = conn.execute("SELECT * FROM web_requests WHERE id=?", (ident,)).fetchone()
                if not row:
                    return self._err(404, "Request not found")
                conn.execute("DELETE FROM web_requests WHERE id=?", (ident,))
                conn.commit()
                return self._send(200, {"ok": True, "deleted": "request", "id": int(ident)})

        return self._err(404, f"Unknown API route {method} {path}")



    def _cascade_delete_customer(self, conn, ident):
        """Remove invoices, jobs, quotes, then the customer. Dependents CASCADE or are unlinked."""
        # Unlink then delete invoices (items/payments ON DELETE CASCADE)
        conn.execute(
            "UPDATE invoices SET job_id=NULL, address_id=NULL WHERE customer_id=?",
            (ident,),
        )
        conn.execute("DELETE FROM invoices WHERE customer_id=?", (ident,))
        # Jobs (materials/notes CASCADE); unlink quote/address first
        conn.execute(
            "UPDATE jobs SET quote_id=NULL, address_id=NULL, tech_id=NULL WHERE customer_id=?",
            (ident,),
        )
        conn.execute("DELETE FROM jobs WHERE customer_id=?", (ident,))
        # Quotes (items CASCADE)
        conn.execute("UPDATE quotes SET address_id=NULL WHERE customer_id=?", (ident,))
        conn.execute("DELETE FROM quotes WHERE customer_id=?", (ident,))
        conn.execute("DELETE FROM web_requests WHERE customer_id=?", (ident,))
        # Addresses CASCADE from customer
        conn.execute("DELETE FROM customers WHERE id=?", (ident,))

    def _cascade_delete_quote(self, conn, ident):
        conn.execute("UPDATE jobs SET quote_id=NULL WHERE quote_id=?", (ident,))
        conn.execute("DELETE FROM quotes WHERE id=?", (ident,))

    def _cascade_delete_job(self, conn, ident):
        conn.execute("UPDATE invoices SET job_id=NULL WHERE job_id=?", (ident,))
        conn.execute("DELETE FROM jobs WHERE id=?", (ident,))

    def _cascade_delete_invoice(self, conn, ident):
        conn.execute("DELETE FROM invoices WHERE id=?", (ident,))

    def _cascade_delete_inventory(self, conn, ident):
        conn.execute("UPDATE quote_items SET inventory_id=NULL WHERE inventory_id=?", (ident,))
        conn.execute("UPDATE job_materials SET inventory_id=NULL WHERE inventory_id=?", (ident,))
        conn.execute("DELETE FROM inventory WHERE id=?", (ident,))

    def _cascade_delete_team(self, conn, ident):
        conn.execute("UPDATE jobs SET tech_id=NULL WHERE tech_id=?", (ident,))
        conn.execute("DELETE FROM team WHERE id=?", (ident,))

    def _replace_quote_items(self, conn, qid, items):
        for it in items:
            conn.execute(
                """INSERT INTO quote_items (quote_id, kind, description, qty, unit, unit_price, inventory_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    qid,
                    it.get("kind") or "labor",
                    it.get("description") or "",
                    money(it.get("qty") or 1),
                    it.get("unit") or "ea",
                    money(it.get("unit_price")),
                    it.get("inventory_id"),
                ),
            )

    def _convert_quote(self, conn, ident):
        q = conn.execute("SELECT * FROM quotes WHERE id=?", (ident,)).fetchone()
        if not q:
            return self._err(404, "Quote not found")
        if q["status"] != "accepted":
            return self._err(400, "Only accepted quotes can convert to a job")
        existing = conn.execute("SELECT * FROM jobs WHERE quote_id=?", (ident,)).fetchone()
        if existing:
            return self._send(200, hydrate_job(conn, existing))
        items = conn.execute("SELECT * FROM quote_items WHERE quote_id=?", (ident,)).fetchall()
        labor = [i for i in items if i["kind"] == "labor"]
        mats = [i for i in items if i["kind"] == "material"]
        scope_bits = [i["description"] for i in labor]
        if mats:
            scope_bits.append("Materials: " + ", ".join(f"{m['qty']:g} {m['unit']} {m['description']}" for m in mats))
        num = store.next_number(conn, "job")
        cur = conn.execute(
            """INSERT INTO jobs (
                 number, customer_id, address_id, quote_id, job_type, status, tech_id,
                 scheduled_date, scheduled_start, scheduled_end, scope, notes, created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                num,
                q["customer_id"],
                q["address_id"],
                q["id"],
                "other",
                "scheduled",
                None,
                None,
                None,
                None,
                "\n".join(scope_bits) or q["notes"],
                q["notes"],
                now_iso(),
            ),
        )
        conn.commit()
        job = hydrate_job(conn, conn.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())
        return self._send(201, job)

    def _invoice_from_job(self, conn, job_id):
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            return self._err(404, "Job not found")
        existing = conn.execute("SELECT * FROM invoices WHERE job_id=?", (job_id,)).fetchone()
        if existing:
            return self._send(200, hydrate_invoice(conn, existing))
        if job["status"] not in ("complete", "billed"):
            return self._err(400, "Complete the job before invoicing")
        s = settings_row(conn)
        num = store.next_number(conn, "invoice")
        issued = now_iso()
        due = (today() + timedelta(days=15)).isoformat()
        cur = conn.execute(
            """INSERT INTO invoices (number, customer_id, job_id, address_id, status, tax_rate, issued_at, due_date, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                num,
                job["customer_id"],
                job["id"],
                job["address_id"],
                "unpaid",
                s["tax_rate"],
                issued,
                due,
                job["scope"],
            ),
        )
        iid = cur.lastrowid
        # line items from quote labor if present, else a labor line, plus job materials
        if job["quote_id"]:
            qitems = conn.execute(
                "SELECT * FROM quote_items WHERE quote_id=?", (job["quote_id"],)
            ).fetchall()
            for it in qitems:
                conn.execute(
                    "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
                    (iid, it["description"], it["qty"], it["unit_price"]),
                )
        else:
            mats = conn.execute("SELECT * FROM job_materials WHERE job_id=?", (job_id,)).fetchall()
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
                (iid, f"Labor — {job['job_type'].replace('_',' ')} ({job['number']})", 1, s["default_labor_rate"] * 2),
            )
            for m in mats:
                markup = money(m["unit_cost"] * 1.45)
                conn.execute(
                    "INSERT INTO invoice_items (invoice_id, description, qty, unit_price) VALUES (?,?,?,?)",
                    (iid, m["description"], m["qty"], markup),
                )
        conn.execute("UPDATE jobs SET status='billed' WHERE id=?", (job_id,))
        conn.commit()
        return self._send(201, hydrate_invoice(conn, conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()))

    def _dashboard(self, conn):
        t = today().isoformat()
        week_start = today() - timedelta(days=today().weekday())
        week_end = week_start + timedelta(days=6)
        jobs_today = [
            hydrate_job(conn, j)
            for j in conn.execute(
                "SELECT * FROM jobs WHERE scheduled_date = ? ORDER BY scheduled_start", (t,)
            ).fetchall()
        ]
        jobs_week = [
            hydrate_job(conn, j)
            for j in conn.execute(
                "SELECT * FROM jobs WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date, scheduled_start",
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
        ]
        quotes_waiting = [
            hydrate_quote(conn, q)
            for q in conn.execute(
                "SELECT * FROM quotes WHERE status='sent' ORDER BY id DESC"
            ).fetchall()
        ]
        open_pipeline = [
            hydrate_quote(conn, q)
            for q in conn.execute(
                "SELECT * FROM quotes WHERE status IN ('draft','sent') ORDER BY id DESC"
            ).fetchall()
        ]
        invoices = [
            hydrate_invoice(conn, i)
            for i in conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
        ]
        overdue = [i for i in invoices if i["status"] == "overdue"]
        unpaid = [i for i in invoices if i["status"] in ("unpaid", "partial", "overdue")]
        cash_in = money(sum(i["balance"] for i in unpaid))
        # payments this month
        month = today().strftime("%Y-%m")
        month_paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE paid_at LIKE ?",
            (month + "%",),
        ).fetchone()["s"]
        pipeline_value = money(sum(q["total"] for q in open_pipeline))
        low_stock = conn.execute(
            "SELECT * FROM inventory WHERE qty_on_hand <= reorder_level ORDER BY qty_on_hand"
        ).fetchall()
        web_new = [
            hydrate_request(conn, r)
            for r in conn.execute(
                "SELECT * FROM web_requests WHERE status='new' ORDER BY id DESC"
            ).fetchall()
        ]
        web_open = [
            hydrate_request(conn, r)
            for r in conn.execute(
                "SELECT * FROM web_requests WHERE status IN ('new','contacted') ORDER BY id DESC"
            ).fetchall()
        ]
        return {
            "today": t,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "jobs_today": jobs_today,
            "jobs_week": jobs_week,
            "quotes_waiting": quotes_waiting,
            "open_pipeline": open_pipeline,
            "pipeline_value": pipeline_value,
            "overdue": overdue,
            "cash_coming_in": cash_in,
            "collected_this_month": money(month_paid),
            "low_stock": low_stock,
            "web_requests": web_open,
            "web_requests_new": web_new,
            "counts": {
                "jobs_today": len(jobs_today),
                "jobs_week": len(jobs_week),
                "quotes_waiting": len(quotes_waiting),
                "overdue": len(overdue),
                "web_requests_new": len(web_new),
            },
        }

    def _public(self, conn, method, ident, sub, subid):
        if ident == "company" and method == "GET":
            return self._send(200, public_company(conn))

        if ident == "requests" and method == "POST":
            body = read_json(self)
            name = (body.get("name") or "").strip()
            phone = (body.get("phone") or "").strip()
            if not name or not phone:
                return self._err(400, "Name and phone are required")
            email = (body.get("email") or "").strip()
            street = (body.get("street") or "").strip()
            city = (body.get("city") or "").strip()
            state = (body.get("state") or "FL").strip() or "FL"
            zipc = (body.get("zip") or "").strip()
            service = (body.get("service") or "other").strip()
            if service not in ("lighting", "panel", "ev", "service", "other"):
                service = "other"
            message = (body.get("message") or "").strip()
            preferred = (body.get("preferred") or "").strip()
            cust = find_customer_by_phone(conn, phone)
            if not cust:
                cur = conn.execute(
                    """INSERT INTO customers (name, kind, phone, email, notes, source, portal_code, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        name,
                        "person",
                        phone,
                        email or None,
                        f"Web request — {service}.",
                        "web",
                        store.new_portal_code(conn),
                        now_iso(),
                    ),
                )
                cid = cur.lastrowid
                if street:
                    conn.execute(
                        "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
                        (cid, "Service", street, city or "", state, zipc),
                    )
            else:
                cid = cust["id"]
                if email and not cust.get("email"):
                    conn.execute("UPDATE customers SET email=? WHERE id=?", (email, cid))
                if street:
                    addrs = conn.execute(
                        "SELECT * FROM addresses WHERE customer_id=?", (cid,)
                    ).fetchall()
                    blob = " ".join(f"{a['street']} {a['city']}" for a in addrs).lower()
                    if street.lower() not in blob:
                        conn.execute(
                            "INSERT INTO addresses (customer_id, label, street, city, state, zip) VALUES (?,?,?,?,?,?)",
                            (cid, "Service", street, city or "", state, zipc),
                        )
                note = cust.get("notes") or ""
                extra = f"Web request — {service}."
                if extra not in note:
                    conn.execute(
                        "UPDATE customers SET notes=? WHERE id=?",
                        ((note + "\n" + extra).strip(), cid),
                    )
            cur = conn.execute(
                """INSERT INTO web_requests (
                     customer_id, name, phone, email, street, city, state, zip,
                     service, message, preferred, status, created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, name, phone, email, street, city, state, zipc,
                    service, message, preferred, "new", now_iso(),
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM web_requests WHERE id=?", (cur.lastrowid,)).fetchone()
            out = hydrate_request(conn, row)
            cust_row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
            return self._send(201, {
                "ok": True,
                "id": out["id"],
                "customer_id": cid,
                "portal_code": cust_row["portal_code"] if cust_row else None,
                "message": "Request received. We will be in touch.",
            })

        if ident == "portal" and method == "POST":
            body = read_json(self)
            cust = None
            code = (body.get("code") or body.get("portal_code") or "").strip()
            if code:
                cust = find_customer_by_portal_code(conn, code)
            if not cust:
                name = (body.get("name") or "").strip()
                phone = (body.get("phone") or "").strip()
                if not name or not phone:
                    return self._err(401, "Name and phone, or a portal code, are required")
                by_phone = find_customer_by_phone(conn, phone)
                if by_phone and names_match(by_phone["name"], name):
                    cust = by_phone
            if not cust:
                return self._err(404, "No matching account. Check the name and phone, or your portal code.")
            if not cust.get("portal_code"):
                conn.execute(
                    "UPDATE customers SET portal_code=? WHERE id=?",
                    (store.new_portal_code(conn), cust["id"]),
                )
                conn.commit()
                cust = conn.execute("SELECT * FROM customers WHERE id=?", (cust["id"],)).fetchone()
            return self._send(200, portal_payload(conn, cust))

        if ident == "invoices" and sub:
            key = sub
            if str(key).isdigit():
                row = conn.execute("SELECT * FROM invoices WHERE id=?", (key,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM invoices WHERE number=?", (key,)).fetchone()
            if not row:
                return self._err(404, "Invoice not found")
            if method == "GET" and not subid:
                return self._send(200, public_invoice_view(conn, row))
            if method == "POST" and subid == "pay":
                body = read_json(self)
                inv = hydrate_invoice(conn, row)
                if inv["balance"] <= 0:
                    return self._err(400, "This invoice is already paid")
                amt = money(body.get("amount", inv["balance"]))
                if amt <= 0:
                    return self._err(400, "Amount must be greater than 0")
                if amt > inv["balance"]:
                    amt = inv["balance"]
                last4 = brand_card(body.get("card_number") or "")
                if not last4:
                    # allow missing PAN if they send a last4/reference (still a recorded shop payment)
                    given = re.sub(r"\D", "", str(body.get("last4") or ""))
                    if len(given) == 4:
                        last4 = f"Card ••{given}"
                    else:
                        return self._err(400, "Enter a valid card number")
                holder = (body.get("cardholder") or body.get("name") or "").strip()
                ref_bits = ["Online checkout", last4]
                if holder:
                    ref_bits.append(holder)
                ref = " · ".join(ref_bits)
                conn.execute(
                    "INSERT INTO payments (invoice_id, amount, method, paid_at, reference) VALUES (?,?,?,?,?)",
                    (inv["id"], amt, "card", now_iso(), ref),
                )
                conn.commit()
                fresh = conn.execute("SELECT * FROM invoices WHERE id=?", (inv["id"],)).fetchone()
                view = public_invoice_view(conn, fresh)
                conn.execute(
                    "UPDATE invoices SET status=? WHERE id=?",
                    (view["status"] if view["status"] != "overdue" else "unpaid", inv["id"]),
                )
                conn.commit()
                view = public_invoice_view(conn, conn.execute("SELECT * FROM invoices WHERE id=?", (inv["id"],)).fetchone())
                return self._send(201, view)

        return self._err(404, f"Unknown public route {method}")

    def _static(self, path: str):
        raw = path.split("?", 1)[0]
        if raw.endswith("/") and raw != "/":
            raw = raw.rstrip("/")
        public_root = PUBLIC.resolve()
        if raw in ("/", "/index.html"):
            file_path = PUBLIC / "index.html"
        elif raw in ("/shop", "/shop/index.html") or raw.startswith("/shop/"):
            file_path = PUBLIC / "shop.html"
        elif raw in ("/portal", "/portal/index.html"):
            file_path = PUBLIC / "portal.html"
        elif raw == "/pay" or raw.startswith("/pay/"):
            file_path = PUBLIC / "pay.html"
        else:
            rel = raw.lstrip("/")
            file_path = (PUBLIC / rel).resolve()
            if not str(file_path).startswith(str(public_root)):
                return self._err(403, "Forbidden")
            if not file_path.is_file():
                return self._err(404, "Not found")
        if not file_path.is_file():
            return self._err(404, "Not found")
        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if file_path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif file_path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        self._send(200, data, ctype)


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"GQ Electrical Services  →  http://localhost:{PORT}   shop  →  /shop")
    print(f"SQLite: {store.DB_PATH}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()


if __name__ == "__main__":
    main()
