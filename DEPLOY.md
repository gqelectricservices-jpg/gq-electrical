# Deploy GQ Electrical on Render

This app is a Python stdlib + SQLite web server. Persistence uses a Render disk mounted at `/app/data` (see `db.py` → `ROOT/data/gq.db`).

## What Render gives you

After you create the service from this Blueprint (`render.yaml`) or by connecting the repo:

1. Render builds the Docker image and starts `python3 server.py`.
2. You get a public URL like **`https://gq-electrical.onrender.com`** (exact subdomain may vary; check the Render dashboard).
3. Free-plan services may sleep when idle; the first request after sleep can take a short cold start.

Do not deploy from this checklist until you are ready — these files only prepare the repo.

## Custom domain: gqelectrical.com (Squarespace DNS)

1. In the Render dashboard → your **gq-electrical** service → **Settings** → **Custom Domains**, add `gqelectrical.com` and/or `www.gqelectrical.com`.
2. Render will show the DNS records it needs (usually a **CNAME** for `www`, and either a **CNAME/ALIAS** or their documented apex option for the root domain).
3. In **Squarespace Domains** → DNS settings for `gqelectrical.com`:
   - **Remove** Squarespace default **A** records that point the apex at Squarespace hosting (they conflict with Render).
   - **Add** the CNAME / ALIAS (and any TXT verification) records exactly as Render instructs.
4. Wait for DNS propagation, then confirm HTTPS shows as active in Render.

## Local check

```bash
cd /workspace/gq-electrical   # or your clone
python3 server.py
# open http://localhost:3000
```

SQLite data stays in `./data/gq.db` locally and under `/app/data` on Render.

## Note on plan + disk

`render.yaml` requests `plan: free` and a 1 GB disk at `/app/data`. Persistent disks on Render typically require a paid web plan (e.g. Starter). If Blueprint apply rejects the free + disk combo, bump `plan` to `starter` (or attach the disk in the dashboard after creating the service).
