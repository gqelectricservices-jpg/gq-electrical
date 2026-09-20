(function () {
  const $ = (s, el = document) => el.querySelector(s);
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function money(n) {
    return (Number(n) || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    const d = String(iso).slice(0, 10);
    const [y, m, day] = d.split("-");
    const dt = new Date(+y, +m - 1, +day);
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function jobType(t) {
    return ({
      service_call: "Service call",
      panel_upgrade: "Panel upgrade",
      lighting: "Lighting",
      ev_charger: "EV charger",
      troubleshooting: "Troubleshooting",
      new_construction: "New construction",
      other: "Other",
    }[t] || t || "Job").replace(/_/g, " ");
  }
  function addr(a) {
    if (!a) return "";
    return [a.street, [a.city, a.state, a.zip].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  }

  const form = $("#lookup");
  const desk = $("#desk");
  const err = $("#err");

  async function lookup(body) {
    err.hidden = true;
    const r = await fetch("/api/public/portal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Not found");
    sessionStorage.setItem("gq-portal", JSON.stringify({
      name: data.customer.name,
      phone: data.customer.phone,
      code: data.customer.portal_code,
    }));
    render(data);
  }

  function render(data) {
    const c = data.customer;
    form.hidden = true;
    desk.hidden = false;
    const quotes = data.quotes || [];
    const jobs = data.jobs || [];
    const invoices = data.invoices || [];
    desk.innerHTML = `
      <div class="row-between" style="margin-bottom:28px">
        <div>
          <p class="eyebrow">Signed in</p>
          <h2 style="font-size:36px">${esc(c.name)}</h2>
          <p class="meta">${esc(c.phone || "")}${c.portal_code ? " · " + esc(c.portal_code) : ""}</p>
        </div>
        <button class="btn-line" type="button" id="out">Sign out</button>
      </div>

      <h3 style="margin:8px 0 4px">Quotes</h3>
      ${quotes.length ? quotes.map((q) => `
        <div class="doc">
          <div>
            <div class="row-between"><strong>${esc(q.number)}</strong><span class="pill">${esc(q.status)}</span></div>
            <div class="meta">${fmtDate(q.created_at)}${q.address ? " · " + esc(addr(q.address)) : ""}</div>
          </div>
          <div class="amt">${money(q.total)}</div>
        </div>`).join("") : `<p class="meta">No quotes on file.</p>`}

      <h3 style="margin:28px 0 4px">Jobs</h3>
      ${jobs.length ? jobs.map((j) => `
        <div class="doc">
          <div>
            <div class="row-between"><strong>${esc(j.number)}</strong><span class="pill">${esc(String(j.status || "").replace(/_/g," "))}</span></div>
            <div class="meta">${esc(jobType(j.job_type))} · ${fmtDate(j.scheduled_date)}${j.tech ? " · " + esc(j.tech.name) : ""}</div>
            ${j.scope ? `<div class="meta" style="margin-top:6px">${esc(j.scope)}</div>` : ""}
          </div>
        </div>`).join("") : `<p class="meta">No jobs on file.</p>`}

      <h3 style="margin:28px 0 4px">Invoices</h3>
      ${invoices.length ? invoices.map((i) => `
        <div class="doc">
          <div>
            <div class="row-between"><strong>${esc(i.number)}</strong><span class="pill">${esc(i.status)}</span></div>
            <div class="meta">Issued ${fmtDate(i.issued_at)} · Due ${fmtDate(i.due_date)}</div>
            <div class="meta">Paid ${money(i.paid)} · Balance ${money(i.balance)}</div>
            ${i.balance > 0 ? `<p style="margin-top:10px"><a class="btn-dark" style="width:auto;min-width:140px;display:inline-flex" href="/pay?n=${encodeURIComponent(i.number)}">Pay ${money(i.balance)}</a></p>` : ""}
          </div>
          <div class="amt">${money(i.total)}</div>
        </div>`).join("") : `<p class="meta">No invoices on file.</p>`}
    `;
    $("#out").onclick = () => {
      sessionStorage.removeItem("gq-portal");
      desk.hidden = true;
      desk.innerHTML = "";
      form.hidden = false;
    };
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      await lookup(body);
    } catch (ex) {
      err.hidden = false;
      err.textContent = ex.message;
    }
  });

  try {
    const saved = JSON.parse(sessionStorage.getItem("gq-portal") || "null");
    if (saved && (saved.code || (saved.name && saved.phone))) {
      lookup(saved).catch(() => sessionStorage.removeItem("gq-portal"));
    }
  } catch (_) {}
})();
