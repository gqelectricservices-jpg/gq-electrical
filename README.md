# GQ Electrical Services

Public site, client portal, and shop office for **GQ Electrical Services** (owner: Gerard Alberta).
Python 3 stdlib + SQLite. Built to be used from a phone.

## Start

```bash
cd /workspace/gq-electrical
python3 server.py
```

Then:

| Surface | Path |
|---|---|
| Public marketing site | **http://localhost:3000/** |
| Shop back office | **http://localhost:3000/shop** |
| Client portal | **http://localhost:3000/portal** |
| Invoice pay | **http://localhost:3000/pay?n=INV-xxxx** |

Data lives in `data/gq.db` (not tracked in git). If the file is missing, the server creates an empty database with only the company settings row — no sample records and no prices.

## How a web request flows

1. Visitor fills **Request a consult** on the public site.
2. Server creates (or matches) a **customer** flagged `source=web`, with a portal code, and a **web_request** row in SQLite.
3. Gerard sees it on the shop **dashboard** (Web requests) and under **Requests**.
4. He can call, open the customer, quote, schedule — the existing shop path.

## Portal & payments

- Portal lookup: **name + phone**, or a **portal code**.
- Quotes, jobs, and invoices for that customer only.
- **Pay** records a `payments` row on the invoice the same way the shop’s “Record payment” does (`method=card`, reference like `Online checkout · Visa ••4242`). No card network is charged. Stripe can be wired later. The shop invoice screen shows the payment immediately.

## Shop office (unchanged modules)

Dashboard, Jobs, Schedule, Quotes, Invoices, Customers, Inventory, Team, Settings — plus **Requests**. Delete buttons remain on every record type.

End-to-end: website request → customer → quote → accept → job → complete → invoice → portal payment.

## Brand

Official artwork in `public/brand/`. Palette: black / white / gray; bright yellow only as a rare accent (the bolt, one public CTA). Tagline: *Where Guaranteed Meets Quality.*
