/* GQ Electrical Services — shop office SPA */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  async function api(path, opts = {}) {
    const r = await fetch("/api" + path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      method: opts.method || "GET",
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { error: text }; }
    if (!r.ok) throw new Error((data && data.error) || r.statusText);
    return data;
  }

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
    const d = iso.slice(0, 10);
    const [y, m, day] = d.split("-");
    const dt = new Date(+y, +m - 1, +day);
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  function fmtWhen(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return fmtDate(iso);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  function phoneHref(p) {
    return "tel:" + String(p || "").replace(/[^\d+]/g, "");
  }
  function addrLine(a) {
    if (!a) return "";
    return [a.street, [a.city, a.state, a.zip].filter(Boolean).join(" ")].filter(Boolean).join(", ");
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
  function statusLabel(s) {
    return String(s || "").replace(/_/g, " ");
  }
  function badge(status) {
    const s = status || "draft";
    return `<span class="badge ${esc(s)}"><span class="dot"></span>${esc(statusLabel(s))}</span>`;
  }
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._id);
    toast._id = setTimeout(() => { t.hidden = true; }, 2600);
  }
  function confirmDelete(kind, name) {
    return window.confirm("Delete " + kind + " " + name + "? This cannot be undone.");
  }
  function bindDelete(btn, { path, kind, name, after }) {
    if (!btn) return;
    btn.addEventListener("click", async () => {
      if (!confirmDelete(kind, name)) return;
      try {
        await api(path, { method: "DELETE" });
        toast("Deleted");
        after();
      } catch (err) {
        toast(err.message || "Could not delete");
      }
    });
  }

  const ICONS = {
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z"/></svg>',
    jobs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 5V4h8v1M8 11h8M8 15h5"/></svg>',
    schedule: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    invoices: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M15 3v5h5M9 13h6M9 17h4"/></svg>',
    more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18" cy="12" r="1.6"/></svg>',
  };

  const TABS = [
    { href: "#/", id: "home", label: "Home", icon: "home" },
    { href: "#/jobs", id: "jobs", label: "Jobs", icon: "jobs" },
    { href: "#/schedule", id: "schedule", label: "Schedule", icon: "schedule" },
    { href: "#/invoices", id: "invoices", label: "Invoices", icon: "invoices" },
    { href: "#/more", id: "more", label: "More", icon: "more" },
  ];
  const SIDE = [
    { href: "#/", id: "home", label: "Dashboard" },
    { href: "#/requests", id: "requests", label: "Requests" },
    { href: "#/jobs", id: "jobs", label: "Jobs" },
    { href: "#/schedule", id: "schedule", label: "Schedule" },
    { href: "#/quotes", id: "quotes", label: "Quotes" },
    { href: "#/invoices", id: "invoices", label: "Invoices" },
    { href: "#/customers", id: "customers", label: "Customers" },
    { href: "#/inventory", id: "inventory", label: "Inventory" },
    { href: "#/team", id: "team", label: "Team" },
    { href: "#/settings", id: "settings", label: "Settings" },
    { href: "#/website", id: "website", label: "Website" },
  ];
  const SHEET = SIDE.filter((x) => !["home", "jobs", "schedule", "invoices"].includes(x.id));

  function activeId(path) {
    if (path.startsWith("/requests")) return "requests";
    if (path.startsWith("/jobs")) return "jobs";
    if (path.startsWith("/schedule")) return "schedule";
    if (path.startsWith("/invoices")) return "invoices";
    if (path.startsWith("/quotes")) return "quotes";
    if (path.startsWith("/customers")) return "customers";
    if (path.startsWith("/inventory")) return "inventory";
    if (path.startsWith("/team")) return "team";
    if (path.startsWith("/settings")) return "settings";
    if (path.startsWith("/website")) return "website";
    return "home";
  }

  function renderNav(path) {
    const id = activeId(path);
    $("#side-nav").innerHTML = SIDE.map((n) =>
      `<a href="${n.href}" class="${n.id === id ? "active" : ""}">${esc(n.label)}</a>`
    ).join("");
    $("#sheet-nav").innerHTML = SHEET.map((n) =>
      `<a href="${n.href}" class="${n.id === id ? "active" : ""}">${esc(n.label)}</a>`
    ).join("");
    $("#tabbar").innerHTML = TABS.map((n) =>
      `<a href="${n.href}" class="${n.id === id || (n.id === "more" && SHEET.some((s) => s.id === id)) ? "active" : ""}">${ICONS[n.icon]}<span>${n.label}</span></a>`
    ).join("");
  }

  function setTitle(t) { $("#top-title").textContent = t; }

  function parseHash() {
    const h = (location.hash || "#/").replace(/^#/, "") || "/";
    const parts = h.split("/").filter(Boolean);
    return { path: "/" + parts.join("/"), parts };
  }

  let viewEl;
  function html(s) { viewEl.innerHTML = s; }

  /* ---------------- Dashboard ---------------- */
  async function pageDashboard() {
    setTitle("Shop office");
    const d = await api("/dashboard");
    html(`
      <h1>Today</h1>
      <p class="lede">${fmtDate(d.today)} · ${d.counts.jobs_today} job${d.counts.jobs_today === 1 ? "" : "s"} on the board</p>
      <div class="grid-stats">
        <div class="card stat"><div class="k">Cash coming in</div><div class="v">${money(d.cash_coming_in)}</div></div>
        <div class="card stat ${d.counts.overdue ? "warn" : ""}"><div class="k">Overdue invoices</div><div class="v">${d.counts.overdue}</div></div>
        <div class="card stat"><div class="k">Quotes waiting</div><div class="v">${d.counts.quotes_waiting}</div></div>
        <div class="card stat"><div class="k">Open pipeline</div><div class="v">${money(d.pipeline_value)}</div></div>
      </div>

      ${(d.web_requests && d.web_requests.length) ? `
      <div class="section"><h2>Web requests</h2><a class="tiny" href="#/requests">All requests →</a></div>
      ${requestList(d.web_requests)}
      ` : ""}

      <div class="section"><h2>Today’s jobs</h2><a class="tiny" href="#/schedule">Week board →</a></div>
      ${d.jobs_today.length ? jobList(d.jobs_today) : `<div class="empty">Nothing scheduled today.</div>`}

      <div class="section"><h2>This week</h2></div>
      ${d.jobs_week.length ? jobList(d.jobs_week) : `<div class="empty">No jobs this week.</div>`}

      <div class="section"><h2>Quotes waiting on a customer</h2><a class="tiny" href="#/quotes">All quotes →</a></div>
      ${d.quotes_waiting.length ? quoteList(d.quotes_waiting) : `<div class="empty">No sent quotes outstanding.</div>`}

      <div class="section"><h2>Overdue invoices</h2><a class="tiny" href="#/invoices">All invoices →</a></div>
      ${d.overdue.length ? invoiceList(d.overdue) : `<div class="empty">Nothing overdue. Good.</div>`}

      ${d.low_stock.length ? `
        <div class="section"><h2>Low stock</h2><a class="tiny" href="#/inventory">Inventory →</a></div>
        <div class="card">${d.low_stock.map((i) => `<div class="row-between" style="padding:6px 0"><span>${esc(i.name)}</span><span class="tiny">${i.qty_on_hand} ${esc(i.unit)}</span></div>`).join("")}</div>
      ` : ""}
    `);
  }

  function jobList(jobs) {
    return `<div class="list">${jobs.map((j) => `
      <a class="item card-link" href="#/jobs/${j.id}">
        <div class="body">
          <div class="row-between"><span class="title">${esc(j.number)} · ${esc(j.customer?.name || "")}</span>${badge(j.status)}</div>
          <div class="meta">${esc(jobType(j.job_type))} · ${fmtDate(j.scheduled_date)}${j.scheduled_start ? " · " + j.scheduled_start : ""}${j.tech ? " · " + esc(j.tech.name) : ""}</div>
          <div class="meta">${esc(addrLine(j.address))}</div>
        </div>
      </a>`).join("")}</div>`;
  }
  function quoteList(qs) {
    return `<div class="list">${qs.map((q) => `
      <a class="item card-link" href="#/quotes/${q.id}">
        <div class="body">
          <div class="row-between"><span class="title">${esc(q.number)} · ${esc(q.customer?.name || "")}</span>${badge(q.status)}</div>
          <div class="meta">${fmtDate(q.created_at)} · ${esc(addrLine(q.address))}</div>
        </div>
        <div class="amt">${money(q.total)}</div>
      </a>`).join("")}</div>`;
  }
  function invoiceList(rows) {
    return `<div class="list">${rows.map((i) => `
      <a class="item card-link" href="#/invoices/${i.id}">
        <div class="body">
          <div class="row-between"><span class="title">${esc(i.number)} · ${esc(i.customer?.name || "")}</span>${badge(i.status)}</div>
          <div class="meta">Due ${fmtDate(i.due_date)}</div>
        </div>
        <div class="amt">${money(i.balance)}</div>
      </a>`).join("")}</div>`;
  }
  function serviceLabel(s) {
    return ({
      lighting: "Lighting",
      panel: "Panel & whole-home",
      ev: "EV charging",
      service: "Repairs & service",
      other: "Other",
    }[s] || s || "Request");
  }
  function requestList(rows) {
    if (!rows.length) return `<div class="empty">No web requests.</div>`;
    return `<div class="list">${rows.map((r) => `
      <a class="item card-link" href="#/requests/${r.id}">
        <div class="body">
          <div class="row-between"><span class="title">${esc(r.name)}</span>${badge(r.status === "new" ? "new" : r.status)}</div>
          <div class="meta">${esc(serviceLabel(r.service))} · ${esc(r.phone || "")}${r.city ? " · " + esc(r.city) : ""}</div>
          <div class="meta">${esc((r.message || "").slice(0, 110))}${(r.message || "").length > 110 ? "…" : ""}</div>
        </div>
      </a>`).join("")}</div>`;
  }

  /* ---------------- Customers ---------------- */
  async function pageCustomers() {
    setTitle("Customers");
    const rows = await api("/customers");
    html(`
      <div class="row-between"><h1>Customers</h1><a class="btn btn-primary" href="#/customers/new">New</a></div>
      <p class="lede">${rows.length} on file</p>
      <input class="search" type="search" id="q" placeholder="Search name, phone, address" />
      <div id="clist">${custCards(rows)}</div>
    `);
    $("#q").addEventListener("input", async (e) => {
      const q = e.target.value.trim();
      const data = await api("/customers" + (q ? "?q=" + encodeURIComponent(q) : ""));
      $("#clist").innerHTML = custCards(data);
    });
  }
  function custCards(rows) {
    if (!rows.length) return `<div class="empty">No customers yet.</div>`;
    return `<div class="list">${rows.map((c) => `
      <a class="item card-link" href="#/customers/${c.id}">
        <div class="body">
          <div class="title">${esc(c.name)}${c.source === "web" ? ` <span class="pill">Web</span>` : ""}</div>
          <div class="meta">${esc(c.kind === "business" ? "Business" : "Residential")} · ${esc(c.phone || "No phone")}</div>
          <div class="meta">${esc(addrLine(c.addresses?.[0]))}</div>
        </div>
      </a>`).join("")}</div>`;
  }

  async function pageCustomer(id, isNew) {
    const [settings] = await Promise.all([api("/settings")]);
    let c = isNew ? { name: "", kind: "person", phone: "", email: "", notes: "", addresses: [] } : await api("/customers/" + id);
    setTitle(isNew ? "New customer" : c.name);
    html(`
      ${isNew ? "<h1>New customer</h1>" : `
        <div class="row-between"><h1>${esc(c.name)}</h1><span class="pill">${c.kind === "business" ? "Business" : "Residential"}</span></div>
        <p class="lede">${esc(c.phone || "")} ${c.email ? " · " + esc(c.email) : ""}${c.source === "web" ? " · Web request" : ""}${c.portal_code ? " · Portal " + esc(c.portal_code) : ""}</p>
        <div class="btn-row no-print" style="margin-bottom:14px">
          ${c.phone ? `<a class="btn btn-ghost" href="${phoneHref(c.phone)}">Call</a>` : ""}
          ${c.email ? `<a class="btn btn-ghost" href="mailto:${esc(c.email)}">Email</a>` : ""}
        </div>
      `}
      <form class="stack" id="cf">
        <label class="field">Name<input name="name" required value="${esc(c.name || "")}" /></label>
        <label class="field">Type
          <select name="kind">
            <option value="person" ${c.kind === "person" ? "selected" : ""}>Residential</option>
            <option value="business" ${c.kind === "business" ? "selected" : ""}>Business</option>
          </select>
        </label>
        <div class="grid-2">
          <label class="field">Phone<input name="phone" type="tel" value="${esc(c.phone || "")}" /></label>
          <label class="field">Email<input name="email" type="email" value="${esc(c.email || "")}" /></label>
        </div>
        <label class="field">Notes<textarea name="notes">${esc(c.notes || "")}</textarea></label>
        ${isNew ? `
          <h3>Service address</h3>
          <label class="field">Street<input name="street" /></label>
          <div class="grid-2">
            <label class="field">City<input name="city" /></label>
            <label class="field">State<input name="state" value="FL" /></label>
          </div>
          <label class="field">ZIP<input name="zip" /></label>
        ` : ""}
        <button class="btn btn-primary" type="submit">${isNew ? "Save customer" : "Save changes"}</button>
        ${!isNew ? `<button class="btn btn-delete no-print" type="button" id="del-rec">Delete customer</button>` : ""}
      </form>
      ${!isNew ? `
        <div class="section"><h2>Addresses</h2></div>
        ${(c.addresses || []).map((a) => `<div class="card"><div class="strong">${esc(a.label || "Service")}</div><div class="addr">${esc(addrLine(a))}</div></div>`).join("") || `<div class="empty">No addresses.</div>`}
        <form class="card stack" id="af" style="margin-top:10px">
          <h3>Add address</h3>
          <label class="field">Label<input name="label" placeholder="Home, Building B…" /></label>
          <label class="field">Street<input name="street" required /></label>
          <div class="grid-2">
            <label class="field">City<input name="city" required /></label>
            <label class="field">State<input name="state" value="${esc(settings.state || "FL")}" /></label>
          </div>
          <label class="field">ZIP<input name="zip" /></label>
          <button class="btn btn-ghost" type="submit">Add address</button>
        </form>
        <div class="section"><h2>Quotes</h2></div>
        ${c.quotes?.length ? quoteList(c.quotes) : `<div class="empty">No quotes.</div>`}
        <div class="section"><h2>Jobs</h2></div>
        ${c.jobs?.length ? jobList(c.jobs) : `<div class="empty">No jobs.</div>`}
        <div class="section"><h2>Invoices</h2></div>
        ${c.invoices?.length ? invoiceList(c.invoices) : `<div class="empty">No invoices.</div>`}
      ` : ""}
    `);
    $("#cf").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      if (isNew) {
        body.address = { street: body.street, city: body.city, state: body.state, zip: body.zip, label: "Service" };
        const created = await api("/customers", { method: "POST", body });
        toast("Customer saved");
        location.hash = "#/customers/" + created.id;
      } else {
        await api("/customers/" + id, { method: "PUT", body });
        toast("Saved");
        pageCustomer(id);
      }
    });
    const af = $("#af");
    if (af) af.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      await api("/customers/" + id + "/addresses", { method: "POST", body });
      toast("Address added");
      pageCustomer(id);
    });
    bindDelete($("#del-rec"), {
      path: "/customers/" + id, kind: "customer", name: c.name,
      after: () => { location.hash = "#/customers"; },
    });
  }

  /* ---------------- Quotes ---------------- */
  async function pageQuotes() {
    setTitle("Quotes");
    const rows = await api("/quotes");
    html(`
      <div class="row-between"><h1>Quotes</h1><a class="btn btn-primary" href="#/quotes/new">New quote</a></div>
      <div class="filter-bar" id="qf">
        ${["all", "draft", "sent", "accepted", "declined"].map((s) => `<button type="button" data-s="${s}" class="${s === "all" ? "on" : ""}">${s}</button>`).join("")}
      </div>
      <div id="ql">${quoteList(rows)}</div>
    `);
    $("#qf").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#qf button").forEach((x) => x.classList.toggle("on", x === b));
      const s = b.dataset.s;
      const show = s === "all" ? rows : rows.filter((r) => r.status === s);
      $("#ql").innerHTML = show.length ? quoteList(show) : `<div class="empty">None.</div>`;
    });
  }

  function itemRows(items, laborRate) {
    const rows = items && items.length ? items : [{ kind: "labor", description: "", qty: 1, unit: "hr", unit_price: laborRate || 125 }];
    return rows.map((it, i) => itemRowHtml(it, i)).join("");
  }
  function itemRowHtml(it, i) {
    return `<tr data-i="${i}">
      <td><select name="kind"><option ${it.kind === "labor" ? "selected" : ""}>labor</option><option ${it.kind === "material" ? "selected" : ""}>material</option></select></td>
      <td><input name="description" value="${esc(it.description || "")}" placeholder="Description" /></td>
      <td><input name="qty" type="number" step="0.01" value="${it.qty ?? 1}" /></td>
      <td><input name="unit" value="${esc(it.unit || "ea")}" /></td>
      <td class="num"><input name="unit_price" type="number" step="0.01" value="${it.unit_price ?? 0}" /></td>
      <td><div class="line-actions"><button type="button" data-del>×</button></div></td>
    </tr>`;
  }

  async function pageQuote(id, isNew) {
    const [customers, settings, inventory] = await Promise.all([
      api("/customers"), api("/settings"), api("/inventory"),
    ]);
    const q = isNew ? {
      status: "draft", notes: "", tax_rate: settings.tax_rate, items: [],
      customer_id: customers[0]?.id, address_id: customers[0]?.addresses?.[0]?.id,
    } : await api("/quotes/" + id);
    setTitle(isNew ? "New quote" : q.number);
    const addrsFor = (cid) => (customers.find((c) => String(c.id) === String(cid)) || {}).addresses || [];

    html(`
      <div class="row-between"><h1>${isNew ? "New quote" : esc(q.number)}</h1>${isNew ? "" : badge(q.status)}</div>
      ${!isNew ? `<p class="lede">${esc(q.customer?.name || "")} · ${money(q.total)}</p>` : ""}
      <form class="stack" id="qf">
        <label class="field">Customer
          <select name="customer_id" id="cust">${customers.map((c) => `<option value="${c.id}" ${String(c.id) === String(q.customer_id) ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
        </label>
        <label class="field">Site address
          <select name="address_id" id="addr"></select>
        </label>
        <label class="field">Status
          <select name="status">
            ${["draft", "sent", "accepted", "declined"].map((s) => `<option value="${s}" ${q.status === s ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </label>
        <label class="field">Notes<textarea name="notes">${esc(q.notes || "")}</textarea></label>
        <label class="field">Tax rate (e.g. 0.06625)<input name="tax_rate" type="number" step="0.00001" value="${q.tax_rate}" /></label>
        <div class="section"><h2>Line items</h2></div>
        <div class="table-wrap card">
          <table class="data" id="items">
            <thead><tr><th>Type</th><th>Description</th><th>Qty</th><th>Unit</th><th class="num">Price</th><th></th></tr></thead>
            <tbody>${itemRows(q.items, settings.default_labor_rate)}</tbody>
          </table>
        </div>
        <div class="btn-row">
          <button class="btn btn-ghost" type="button" id="add-labor">+ Labor</button>
          <button class="btn btn-ghost" type="button" id="add-mat">+ Material</button>
        </div>
        <label class="field">Pull from inventory
          <select id="invpick">
            <option value="">Choose a material…</option>
            ${inventory.map((i) => `<option value="${i.id}" data-name="${esc(i.name)}" data-cost="${i.unit_cost}" data-unit="${esc(i.unit)}">${esc(i.name)} — ${money(i.unit_cost)}/${esc(i.unit)}</option>`).join("")}
          </select>
        </label>
        <div class="card" id="totals"></div>
        <button class="btn btn-primary" type="submit">Save quote</button>
        ${!isNew ? `<button class="btn btn-delete no-print" type="button" id="del-rec">Delete quote</button>` : ""}
      </form>
      ${!isNew && q.status === "accepted" ? `<button class="btn btn-block" style="margin-top:10px" id="convert" type="button">Convert to job</button>` : ""}
      ${!isNew && q.status === "sent" ? `<p class="tiny" style="margin-top:10px">Mark accepted, save, then convert to a job.</p>` : ""}
    `);

    const fillAddr = () => {
      const cid = $("#cust").value;
      const addrs = addrsFor(cid);
      $("#addr").innerHTML = addrs.map((a) =>
        `<option value="${a.id}" ${String(a.id) === String(q.address_id) ? "selected" : ""}>${esc(a.label || "")} — ${esc(addrLine(a))}</option>`
      ).join("") || `<option value="">No address on file</option>`;
    };
    fillAddr();
    $("#cust").addEventListener("change", fillAddr);

    const tbody = $("#items tbody");
    function readItems() {
      return $$("tr", tbody).map((tr) => ({
        kind: $("[name=kind]", tr).value,
        description: $("[name=description]", tr).value,
        qty: +$("[name=qty]", tr).value || 0,
        unit: $("[name=unit]", tr).value,
        unit_price: +$("[name=unit_price]", tr).value || 0,
      }));
    }
    function refreshTotals() {
      const items = readItems();
      const sub = items.reduce((s, i) => s + i.qty * i.unit_price, 0);
      const tax = sub * (+$("[name=tax_rate]").value || 0);
      $("#totals").innerHTML = `<div class="row-between"><span>Subtotal</span><strong>${money(sub)}</strong></div>
        <div class="row-between"><span>Tax</span><strong>${money(tax)}</strong></div>
        <div class="row-between"><span>Total</span><strong>${money(sub + tax)}</strong></div>`;
    }
    tbody.addEventListener("input", refreshTotals);
    tbody.addEventListener("click", (e) => {
      if (e.target.dataset.del !== undefined) { e.target.closest("tr").remove(); refreshTotals(); }
    });
    $("#add-labor").onclick = () => {
      tbody.insertAdjacentHTML("beforeend", itemRowHtml({ kind: "labor", qty: 1, unit: "hr", unit_price: settings.default_labor_rate }));
    };
    $("#add-mat").onclick = () => {
      tbody.insertAdjacentHTML("beforeend", itemRowHtml({ kind: "material", qty: 1, unit: "ea", unit_price: 0 }));
    };
    $("#invpick").onchange = (e) => {
      const opt = e.target.selectedOptions[0];
      if (!opt.value) return;
      const markup = +(opt.dataset.cost || 0) * 1.45;
      tbody.insertAdjacentHTML("beforeend", itemRowHtml({
        kind: "material", description: opt.dataset.name, qty: 1, unit: opt.dataset.unit, unit_price: Math.round(markup * 100) / 100,
        inventory_id: opt.value,
      }));
      e.target.value = "";
      refreshTotals();
    };
    refreshTotals();

    $("#qf").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = {
        customer_id: +fd.get("customer_id"),
        address_id: fd.get("address_id") ? +fd.get("address_id") : null,
        status: fd.get("status"),
        notes: fd.get("notes"),
        tax_rate: +fd.get("tax_rate"),
        items: readItems(),
      };
      if (isNew) {
        const created = await api("/quotes", { method: "POST", body });
        toast("Quote " + created.number + " saved");
        location.hash = "#/quotes/" + created.id;
      } else {
        await api("/quotes/" + id, { method: "PUT", body });
        toast("Quote saved");
        pageQuote(id);
      }
    });
    const cv = $("#convert");
    if (cv) cv.onclick = async () => {
      const job = await api("/quotes/" + id + "/convert", { method: "POST" });
      toast("Job " + job.number + " created");
      location.hash = "#/jobs/" + job.id;
    };
    bindDelete($("#del-rec"), {
      path: "/quotes/" + id, kind: "quote", name: q.number,
      after: () => { location.hash = "#/quotes"; },
    });
  }

  /* ---------------- Jobs ---------------- */
  async function pageJobs() {
    setTitle("Jobs");
    const rows = await api("/jobs");
    html(`
      <div class="row-between"><h1>Jobs</h1><a class="btn btn-primary" href="#/jobs/new">New job</a></div>
      <div class="filter-bar" id="jf">
        ${["all", "scheduled", "in_progress", "complete", "billed"].map((s) => `<button type="button" data-s="${s}" class="${s === "all" ? "on" : ""}">${statusLabel(s)}</button>`).join("")}
      </div>
      <div id="jl">${jobList(rows)}</div>
    `);
    $("#jf").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#jf button").forEach((x) => x.classList.toggle("on", x === b));
      const s = b.dataset.s;
      const show = s === "all" ? rows : rows.filter((r) => r.status === s);
      $("#jl").innerHTML = show.length ? jobList(show) : `<div class="empty">None.</div>`;
    });
  }

  async function pageJob(id, isNew) {
    const [customers, team, settings, inventory] = await Promise.all([
      api("/customers"), api("/team"), api("/settings"), api("/inventory"),
    ]);
    const techs = team.filter((t) => t.role === "technician" || t.role === "owner");
    const j = isNew ? {
      status: "scheduled", job_type: "service_call", notes: "", scope: "",
      customer_id: customers[0]?.id, materials: [], job_notes: [],
    } : await api("/jobs/" + id);
    setTitle(isNew ? "New job" : j.number);
    const addrsFor = (cid) => (customers.find((c) => String(c.id) === String(cid)) || {}).addresses || [];

    html(`
      <div class="row-between"><h1>${isNew ? "New work order" : esc(j.number)}</h1>${isNew ? "" : badge(j.status)}</div>
      ${!isNew ? `<p class="lede">${esc(j.customer?.name || "")} · ${esc(jobType(j.job_type))}${j.tech ? " · " + esc(j.tech.name) : ""}</p>` : ""}
      <form class="stack" id="jf">
        <label class="field">Customer
          <select name="customer_id" id="cust">${customers.map((c) => `<option value="${c.id}" ${String(c.id) === String(j.customer_id) ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
        </label>
        <label class="field">Site<select name="address_id" id="addr"></select></label>
        <label class="field">Job type
          <select name="job_type">
            ${["service_call","panel_upgrade","lighting","ev_charger","troubleshooting","new_construction","other"].map((t) =>
              `<option value="${t}" ${j.job_type === t ? "selected" : ""}>${esc(jobType(t))}</option>`).join("")}
          </select>
        </label>
        <label class="field">Status
          <select name="status">
            ${["scheduled","in_progress","complete","billed"].map((s) => `<option value="${s}" ${j.status === s ? "selected" : ""}>${statusLabel(s)}</option>`).join("")}
          </select>
        </label>
        <label class="field">Technician
          <select name="tech_id">
            <option value="">Unassigned</option>
            ${techs.map((t) => `<option value="${t.id}" ${String(t.id) === String(j.tech_id) ? "selected" : ""}>${esc(t.name)}</option>`).join("")}
          </select>
        </label>
        <label class="field">Date<input name="scheduled_date" type="date" value="${esc(j.scheduled_date || "")}" /></label>
        <div class="grid-2">
          <label class="field">Start<input name="scheduled_start" type="time" value="${esc(j.scheduled_start || "")}" /></label>
          <label class="field">End<input name="scheduled_end" type="time" value="${esc(j.scheduled_end || "")}" /></label>
        </div>
        <label class="field">Scope of work<textarea name="scope">${esc(j.scope || "")}</textarea></label>
        <label class="field">Internal notes<textarea name="notes">${esc(j.notes || "")}</textarea></label>
        <button class="btn btn-primary" type="submit">${isNew ? "Create job" : "Save job"}</button>
        ${!isNew ? `<button class="btn btn-delete no-print" type="button" id="del-rec">Delete job</button>` : ""}
      </form>

      ${!isNew ? `
        <div class="section"><h2>Materials pulled</h2></div>
        <div class="card">
          ${(j.materials || []).length ? `<table class="data"><thead><tr><th>Item</th><th class="num">Qty</th><th></th></tr></thead><tbody>
            ${j.materials.map((m) => `<tr><td>${esc(m.description)}</td><td class="num">${m.qty} ${esc(m.unit || "")}</td>
              <td><button class="btn btn-ghost" style="min-height:36px" data-rm="${m.id}" type="button">Return</button></td></tr>`).join("")}
          </tbody></table>` : `<p class="tiny">Nothing pulled yet. Pulling stock decrements on-hand qty.</p>`}
          <form id="mf" class="stack" style="margin-top:12px">
            <label class="field">Pull from inventory
              <select name="inventory_id" required>
                <option value="">Select material…</option>
                ${inventory.map((i) => `<option value="${i.id}">${esc(i.name)} (${i.qty_on_hand} ${esc(i.unit)} on hand)</option>`).join("")}
              </select>
            </label>
            <label class="field">Qty<input name="qty" type="number" step="0.01" value="1" required /></label>
            <button class="btn btn-ghost" type="submit">Pull onto job</button>
          </form>
        </div>

        <div class="section"><h2>Job notes</h2></div>
        ${(j.job_notes || []).map((n) => `<div class="card"><div class="tiny">${fmtWhen(n.created_at)}</div>${esc(n.body)}</div>`).join("") || `<div class="empty">No notes.</div>`}
        <form id="nf" class="stack" style="margin-top:8px">
          <label class="field">Add note<textarea name="body" required></textarea></label>
          <button class="btn btn-ghost" type="submit">Add note</button>
        </form>

        <div class="btn-row" style="margin-top:16px">
          ${j.status === "complete" && !j.invoice ? `<button class="btn btn-primary" id="bill" type="button">Create invoice</button>` : ""}
          ${j.invoice ? `<a class="btn" href="#/invoices/${j.invoice.id}">Invoice ${esc(j.invoice.number)}</a>` : ""}
          ${j.quote ? `<a class="btn btn-ghost" href="#/quotes/${j.quote.id}">Quote ${esc(j.quote.number)}</a>` : ""}
        </div>
      ` : ""}
    `);

    const fillAddr = () => {
      const cid = $("#cust").value;
      const addrs = addrsFor(cid);
      $("#addr").innerHTML = addrs.map((a) =>
        `<option value="${a.id}" ${String(a.id) === String(j.address_id) ? "selected" : ""}>${esc(a.label || "")} — ${esc(addrLine(a))}</option>`
      ).join("") || `<option value="">No address</option>`;
    };
    fillAddr();
    $("#cust").addEventListener("change", fillAddr);

    $("#jf").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.customer_id = +body.customer_id;
      body.address_id = body.address_id ? +body.address_id : null;
      body.tech_id = body.tech_id ? +body.tech_id : null;
      if (isNew) {
        const created = await api("/jobs", { method: "POST", body });
        toast("Job " + created.number + " created");
        location.hash = "#/jobs/" + created.id;
      } else {
        await api("/jobs/" + id, { method: "PUT", body });
        toast("Job saved");
        pageJob(id);
      }
    });
    const mf = $("#mf");
    if (mf) mf.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.inventory_id = +body.inventory_id;
      body.qty = +body.qty;
      await api("/jobs/" + id + "/materials", { method: "POST", body });
      toast("Material pulled — stock updated");
      pageJob(id);
    });
    $$("[data-rm]").forEach((b) => b.onclick = async () => {
      await api("/jobs/" + id + "/materials/" + b.dataset.rm, { method: "DELETE" });
      toast("Returned to stock");
      pageJob(id);
    });
    const nf = $("#nf");
    if (nf) nf.addEventListener("submit", async (e) => {
      e.preventDefault();
      await api("/jobs/" + id + "/notes", { method: "POST", body: { body: new FormData(e.target).get("body") } });
      toast("Note added");
      pageJob(id);
    });
    const bill = $("#bill");
    if (bill) bill.onclick = async () => {
      const inv = await api("/jobs/" + id + "/invoice", { method: "POST" });
      toast("Invoice " + inv.number + " created");
      location.hash = "#/invoices/" + inv.id;
    };
    bindDelete($("#del-rec"), {
      path: "/jobs/" + id, kind: "job", name: j.number,
      after: () => { location.hash = "#/jobs"; },
    });
  }

  /* ---------------- Schedule ---------------- */
  async function pageSchedule() {
    setTitle("Schedule");
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const weekParam = params.get("week");
    const data = await api("/schedule" + (weekParam ? "?week=" + weekParam : ""));
    const start = new Date(data.week_start + "T00:00:00");
    const prev = new Date(start); prev.setDate(prev.getDate() - 7);
    const next = new Date(start); next.setDate(next.getDate() + 7);
    const today = new Date().toISOString().slice(0, 10);
    let selected = data.days.includes(today) ? today : data.days[0];

    const jobsBy = {};
    data.jobs.forEach((j) => {
      const k = (j.tech_id || "none") + "|" + j.scheduled_date;
      (jobsBy[k] ||= []).push(j);
    });

    html(`
      <div class="week-nav">
        <a class="icon-btn" href="#/schedule?week=${prev.toISOString().slice(0,10)}" aria-label="Previous week">‹</a>
        <h1>Week of ${fmtDate(data.week_start)}</h1>
        <a class="icon-btn" href="#/schedule?week=${next.toISOString().slice(0,10)}" aria-label="Next week">›</a>
      </div>
      <div class="mob-sched">
        <div class="day-chips" id="chips">
          ${data.days.map((d) => {
            const dt = new Date(d + "T00:00:00");
            const wd = dt.toLocaleDateString("en-US", { weekday: "short" });
            return `<button type="button" class="day-chip ${d === selected ? "on" : ""} ${d === today ? "today" : ""}" data-d="${d}"><span>${wd}</span><span class="n">${dt.getDate()}</span></button>`;
          }).join("")}
        </div>
        <div id="daylist"></div>
      </div>
      <div class="desk-grid">
        <table>
          <thead><tr><th></th>${data.days.map((d) => {
            const dt = new Date(d + "T00:00:00");
            return `<th>${dt.toLocaleDateString("en-US", { weekday: "short" })} ${dt.getDate()}</th>`;
          }).join("")}</tr></thead>
          <tbody>
            ${data.technicians.map((t) => `<tr>
              <th><span class="tech-head"><span class="tech-swatch" style="background:${esc(t.color || "#231f20")}"></span>${esc(t.name)}</span></th>
              ${data.days.map((d) => `<td>${(jobsBy[t.id + "|" + d] || []).map((j) =>
                `<a class="job-chip" href="#/jobs/${j.id}"><div class="t">${esc(j.scheduled_start || "")} ${esc(j.number)}</div>${esc(j.customer?.name || "")}<div class="tiny">${esc(jobType(j.job_type))}</div></a>`
              ).join("") || `<span class="tiny">—</span>`}</td>`).join("")}
            </tr>`).join("")}
            <tr>
              <th>Unassigned</th>
              ${data.days.map((d) => `<td>${(jobsBy["none|" + d] || []).map((j) =>
                `<a class="job-chip" href="#/jobs/${j.id}"><div class="t">${esc(j.number)}</div>${esc(j.customer?.name || "")}</a>`
              ).join("") || `<span class="tiny">—</span>`}</td>`).join("")}
            </tr>
          </tbody>
        </table>
      </div>
      <p class="tiny" style="margin-top:12px">Tap a job to reassign the tech or move the day.</p>
    `);

    const renderDay = () => {
      const dayJobs = data.jobs.filter((j) => j.scheduled_date === selected);
      $("#daylist").innerHTML = data.technicians.map((t) => {
        const js = dayJobs.filter((j) => j.tech_id === t.id);
        return `<div class="sched-block">
          <div class="tech-head"><span class="tech-swatch" style="background:${esc(t.color || "#231f20")}"></span>${esc(t.name)}</div>
          ${js.length ? jobList(js) : `<div class="empty">Open</div>`}
        </div>`;
      }).join("") + (() => {
        const u = dayJobs.filter((j) => !j.tech_id);
        return u.length ? `<div class="sched-block"><div class="tech-head">Unassigned</div>${jobList(u)}</div>` : "";
      })();
    };
    renderDay();
    $("#chips")?.addEventListener("click", (e) => {
      const b = e.target.closest(".day-chip");
      if (!b) return;
      selected = b.dataset.d;
      $$(".day-chip").forEach((x) => x.classList.toggle("on", x === b));
      renderDay();
    });
  }

  /* ---------------- Invoices ---------------- */
  async function pageInvoices() {
    setTitle("Invoices");
    const rows = await api("/invoices");
    html(`
      <div class="row-between"><h1>Invoices</h1></div>
      <p class="lede">Create invoices from a completed job.</p>
      <div class="filter-bar" id="inf">
        ${["all", "unpaid", "partial", "overdue", "paid"].map((s) => `<button type="button" data-s="${s}" class="${s === "all" ? "on" : ""}">${s}</button>`).join("")}
      </div>
      <div id="il">${invoiceList(rows)}</div>
    `);
    $("#inf").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#inf button").forEach((x) => x.classList.toggle("on", x === b));
      const s = b.dataset.s;
      const show = s === "all" ? rows : rows.filter((r) => r.status === s);
      $("#il").innerHTML = show.length ? invoiceList(show) : `<div class="empty">None.</div>`;
    });
  }

  async function pageInvoice(id, printMode) {
    const inv = await api("/invoices/" + id);
    const co = inv.company || {};
    setTitle(printMode ? "Print " + inv.number : inv.number);
    if (printMode) {
      html(`
        <div class="print-sheet card">
          <div class="print-head">
            <img class="lockup" src="/brand/logo-stacked.svg" alt="GQ Electrical Services" />
            <div class="print-meta">
              <strong>${esc(inv.number)}</strong>
              ${esc(co.company_name || "GQ Electrical Services")}<br/>
              ${esc(co.street || "")}<br/>${esc([co.city, co.state, co.zip].filter(Boolean).join(" "))}<br/>
              ${esc(co.phone || "")}<br/>${esc(co.email || "")}<br/>
              License ${esc(co.license_no || "")}
            </div>
          </div>
          <div class="grid-2">
            <div>
              <h2>Bill to</h2>
              <div class="strong">${esc(inv.customer?.name || "")}</div>
              <div class="addr">${esc(addrLine(inv.address))}</div>
            </div>
            <div>
              <h2>Invoice</h2>
              <div>Issued ${fmtDate(inv.issued_at)}</div>
              <div>Due ${fmtDate(inv.due_date)}</div>
              ${inv.job ? `<div>Job ${esc(inv.job.number)}</div>` : ""}
              <div style="margin-top:8px">${badge(inv.status)}</div>
            </div>
          </div>
          <div class="table-wrap" style="margin-top:16px">
            <table class="data">
              <thead><tr><th>Description</th><th class="num">Qty</th><th class="num">Price</th><th class="num">Amount</th></tr></thead>
              <tbody>
                ${(inv.items || []).map((it) => `<tr>
                  <td>${esc(it.description)}</td><td class="num">${it.qty}</td>
                  <td class="num">${money(it.unit_price)}</td>
                  <td class="num">${money(it.qty * it.unit_price)}</td>
                </tr>`).join("")}
              </tbody>
            </table>
          </div>
          <div class="totals">
            <div><span>Subtotal</span><span>${money(inv.subtotal)}</span></div>
            <div><span>Tax</span><span>${money(inv.tax)}</span></div>
            <div class="grand"><span>Total</span><span>${money(inv.total)}</span></div>
            <div><span>Paid</span><span>${money(inv.paid)}</span></div>
            <div class="grand"><span>Balance due</span><span>${money(inv.balance)}</span></div>
          </div>
          <p class="tiny" style="margin-top:24px">${esc(co.invoice_footer || "")}</p>
          <p class="tiny">Where Guaranteed Meets Quality.</p>
          <div class="btn-row no-print" style="margin-top:16px">
            <button class="btn btn-primary" type="button" onclick="window.print()">Print</button>
            <a class="btn btn-ghost" href="#/invoices/${inv.id}">Back</a>
          </div>
        </div>
      `);
      return;
    }

    html(`
      <div class="row-between"><h1>${esc(inv.number)}</h1>${badge(inv.status)}</div>
      <p class="lede">${esc(inv.customer?.name || "")} · Balance ${money(inv.balance)}</p>
      <div class="card">
        <div class="row-between"><span>Total</span><strong>${money(inv.total)}</strong></div>
        <div class="row-between"><span>Paid</span><span>${money(inv.paid)}</span></div>
        <div class="row-between"><span>Due ${fmtDate(inv.due_date)}</span><strong>${money(inv.balance)}</strong></div>
      </div>
      <div class="table-wrap card" style="margin-top:10px">
        <table class="data">
          <thead><tr><th>Description</th><th class="num">Qty</th><th class="num">Amount</th></tr></thead>
          <tbody>${(inv.items || []).map((it) => `<tr><td>${esc(it.description)}</td><td class="num">${it.qty}</td><td class="num">${money(it.qty * it.unit_price)}</td></tr>`).join("")}</tbody>
        </table>
      </div>
      <div class="section"><h2>Payments</h2></div>
      ${(inv.payments || []).length ? inv.payments.map((p) => `<div class="card row-between"><span>${esc(p.method)} · ${fmtWhen(p.paid_at)}${p.reference ? " · " + esc(p.reference) : ""}</span><strong>${money(p.amount)}</strong></div>`).join("") : `<div class="empty">No payments recorded.</div>`}
      ${inv.balance > 0 ? `
        <form class="card stack" id="pf" style="margin-top:10px">
          <h3>Record payment</h3>
          <label class="field">Amount<input name="amount" type="number" step="0.01" value="${inv.balance}" required /></label>
          <label class="field">Method
            <select name="method">
              <option>check</option><option>cash</option><option>card</option><option>ach</option><option>other</option>
            </select>
          </label>
          <label class="field">Reference / check #<input name="reference" /></label>
          <button class="btn btn-primary" type="submit">Record payment</button>
        </form>` : ""}
      <div class="btn-row" style="margin-top:14px">
        <a class="btn btn-primary" href="#/invoices/${inv.id}/print">Print invoice</a>
        ${inv.job_id ? `<a class="btn btn-ghost" href="#/jobs/${inv.job_id}">Open job</a>` : ""}
        ${inv.balance > 0 ? `<a class="btn btn-ghost" href="/pay?n=${encodeURIComponent(inv.number)}">Client pay link</a>` : ""}
      </div>
      <button class="btn btn-delete no-print" type="button" id="del-rec">Delete invoice</button>
    `);
    const pf = $("#pf");
    if (pf) pf.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.amount = +body.amount;
      await api("/invoices/" + id + "/payments", { method: "POST", body });
      toast("Payment recorded");
      pageInvoice(id);
    });
    bindDelete($("#del-rec"), {
      path: "/invoices/" + id, kind: "invoice", name: inv.number,
      after: () => { location.hash = "#/invoices"; },
    });
  }

  /* ---------------- Inventory ---------------- */
  async function pageInventory() {
    setTitle("Inventory");
    const rows = await api("/inventory");
    html(`
      <div class="row-between"><h1>Inventory</h1><button class="btn btn-primary" id="ni" type="button">Add item</button></div>
      <p class="lede">Pulling materials onto a job decrements qty on hand.</p>
      <div class="list">
        ${rows.map((i) => `
          <form class="item" data-id="${i.id}">
            <div class="body">
              <div class="row-between"><span class="title">${esc(i.name)}</span>${i.low ? `<span class="badge overdue"><span class="dot"></span>Low</span>` : `<span class="pill">${esc(i.category)}</span>`}</div>
              <div class="meta">${esc(i.sku || "")} · ${money(i.unit_cost)} / ${esc(i.unit)}</div>
              <div class="grid-2" style="margin-top:8px">
                <label class="field">On hand<input name="qty_on_hand" type="number" step="0.01" value="${i.qty_on_hand}" /></label>
                <label class="field">Reorder at<input name="reorder_level" type="number" step="0.01" value="${i.reorder_level}" /></label>
              </div>
              <input type="hidden" name="sku" value="${esc(i.sku || "")}" />
              <input type="hidden" name="name" value="${esc(i.name)}" />
              <input type="hidden" name="category" value="${esc(i.category)}" />
              <input type="hidden" name="unit" value="${esc(i.unit)}" />
              <input type="hidden" name="unit_cost" value="${i.unit_cost}" />
              <button class="btn btn-ghost" type="submit" style="margin-top:8px">Update stock</button>
              <button class="btn btn-delete" type="button" data-del-inv="${i.id}" data-name="${esc(i.name)}">Delete item</button>
            </div>
          </form>`).join("")}
      </div>
      <form class="card stack" id="newinv" hidden style="margin-top:12px">
        <h3>New material</h3>
        <label class="field">Name<input name="name" required /></label>
        <div class="grid-2">
          <label class="field">SKU<input name="sku" /></label>
          <label class="field">Category
            <select name="category">
              ${["wire","breakers","devices","fixtures","conduit","panels","fittings","other"].map((c) => `<option>${c}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="grid-2">
          <label class="field">Unit<input name="unit" value="ea" /></label>
          <label class="field">Unit cost<input name="unit_cost" type="number" step="0.01" value="0" /></label>
        </div>
        <div class="grid-2">
          <label class="field">Qty on hand<input name="qty_on_hand" type="number" step="0.01" value="0" /></label>
          <label class="field">Reorder level<input name="reorder_level" type="number" step="0.01" value="0" /></label>
        </div>
        <button class="btn btn-primary" type="submit">Save item</button>
      </form>
    `);
    $$("form.item").forEach((f) => f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(f).entries());
      await api("/inventory/" + f.dataset.id, { method: "PUT", body });
      toast("Stock updated");
      pageInventory();
    }));
    $$("[data-del-inv]").forEach((b) => bindDelete(b, {
      path: "/inventory/" + b.dataset.delInv, kind: "inventory item", name: b.dataset.name,
      after: () => pageInventory(),
    }));
    $("#ni").onclick = () => { $("#newinv").hidden = false; };
    $("#newinv").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      await api("/inventory", { method: "POST", body });
      toast("Item added");
      pageInventory();
    });
  }

  /* ---------------- Team ---------------- */
  async function pageTeam() {
    setTitle("Team");
    const rows = await api("/team");
    html(`
      <div class="row-between"><h1>Team</h1></div>
      <p class="lede">Used on the dispatch board and work orders.</p>
      <div class="list">
        ${rows.map((t) => `
          <form class="item" data-id="${t.id}">
            <span class="tech-swatch" style="background:${esc(t.color || "#231f20")};margin-top:8px"></span>
            <div class="body stack">
              <label class="field">Name<input name="name" value="${esc(t.name)}" /></label>
              <label class="field">Role
                <select name="role">
                  ${["owner","technician","office"].map((r) => `<option ${t.role === r ? "selected" : ""}>${r}</option>`).join("")}
                </select>
              </label>
              <div class="grid-2">
                <label class="field">Phone<input name="phone" value="${esc(t.phone || "")}" /></label>
                <label class="field">Email<input name="email" value="${esc(t.email || "")}" /></label>
              </div>
              <label class="field">Color<input name="color" value="${esc(t.color || "#231f20")}" /></label>
              <button class="btn btn-ghost" type="submit">Save</button>
              <button class="btn btn-delete" type="button" data-del-team="${t.id}" data-name="${esc(t.name)}">Delete member</button>
            </div>
          </form>`).join("")}
      </div>
      <form class="card stack" id="nt" style="margin-top:12px">
        <h3>Add person</h3>
        <label class="field">Name<input name="name" required /></label>
        <label class="field">Role
          <select name="role"><option>technician</option><option>office</option><option>owner</option></select>
        </label>
        <div class="grid-2">
          <label class="field">Phone<input name="phone" /></label>
          <label class="field">Email<input name="email" /></label>
        </div>
        <button class="btn btn-primary" type="submit">Add to team</button>
      </form>
    `);
    $$("form.item").forEach((f) => f.addEventListener("submit", async (e) => {
      e.preventDefault();
      await api("/team/" + f.dataset.id, { method: "PUT", body: Object.fromEntries(new FormData(f).entries()) });
      toast("Saved");
      pageTeam();
    }));
    $$("[data-del-team]").forEach((b) => bindDelete(b, {
      path: "/team/" + b.dataset.delTeam, kind: "team member", name: b.dataset.name,
      after: () => pageTeam(),
    }));
    $("#nt").addEventListener("submit", async (e) => {
      e.preventDefault();
      await api("/team", { method: "POST", body: Object.fromEntries(new FormData(e.target).entries()) });
      toast("Added");
      pageTeam();
    });
  }

  /* ---------------- Settings ---------------- */
  async function pageSettings() {
    setTitle("Settings");
    const s = await api("/settings");
    html(`
      <h1>Company settings</h1>
      <p class="lede">These print on invoices and set default rates. Public homepage copy is under <a href="#/website">Website</a>.</p>
      <form class="stack" id="sf">
        <label class="field">Company name<input name="company_name" value="${esc(s.company_name)}" /></label>
        <label class="field">License #<input name="license_no" value="${esc(s.license_no || "")}" /></label>
        <div class="grid-2">
          <label class="field">Phone<input name="phone" value="${esc(s.phone || "")}" /></label>
          <label class="field">Email<input name="email" value="${esc(s.email || "")}" /></label>
        </div>
        <label class="field">Street<input name="street" value="${esc(s.street || "")}" /></label>
        <div class="grid-2">
          <label class="field">City<input name="city" value="${esc(s.city || "")}" /></label>
          <label class="field">State<input name="state" value="${esc(s.state || "")}" /></label>
        </div>
        <label class="field">ZIP<input name="zip" value="${esc(s.zip || "")}" /></label>
        <label class="field">Service area<textarea name="service_area">${esc(s.service_area || "")}</textarea></label>
        <div class="grid-2">
          <label class="field">Default labor rate ($/hr)<input name="default_labor_rate" type="number" step="0.01" value="${s.default_labor_rate}" /></label>
          <label class="field">Tax rate<input name="tax_rate" type="number" step="0.00001" value="${s.tax_rate}" /></label>
        </div>
        <label class="field">Invoice footer<textarea name="invoice_footer">${esc(s.invoice_footer || "")}</textarea></label>
        <button class="btn btn-primary" type="submit">Save settings</button>
      </form>
    `);
    $("#sf").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.default_labor_rate = +body.default_labor_rate;
      body.tax_rate = +body.tax_rate;
      await api("/settings", { method: "PUT", body });
      toast("Settings saved");
    });
  }

  /* ---------------- Website (public marketing copy) ---------------- */
  async function pageWebsite() {
    setTitle("Website");
    const s = await api("/settings");
    html(`
      <h1>Website</h1>
      <p class="lede">Edit what visitors see on the public site. Changes appear on the public site after save.</p>
      <p class="lede" style="margin-top:-8px"><a href="/" target="_blank" rel="noopener">Open public site ↗</a></p>
      <form class="stack" id="wf">
        <label class="field">Company name<input name="company_name" value="${esc(s.company_name || "")}" /></label>
        <label class="field">Tagline<input name="tagline" value="${esc(s.tagline || "")}" placeholder="Where Guaranteed Meets Quality." /></label>
        <div class="grid-2">
          <label class="field">Phone<input name="phone" value="${esc(s.phone || "")}" /></label>
          <label class="field">Email<input name="email" value="${esc(s.email || "")}" /></label>
        </div>
        <label class="field">City / location line<input name="location_line" value="${esc(s.location_line || "")}" placeholder="Sanford, Florida" /></label>
        <label class="field">Service area<textarea name="service_area" rows="2">${esc(s.service_area || "")}</textarea></label>
        <label class="field">Hero headline<input name="hero_headline" value="${esc(s.hero_headline || "")}" /></label>
        <label class="field">Hero subhead / short pitch<textarea name="hero_subhead" rows="3">${esc(s.hero_subhead || "")}</textarea></label>
        <label class="field">About / process blurb<textarea name="about_blurb" rows="5" placeholder="Paragraph 1…\n\nParagraph 2…">${esc(s.about_blurb || "")}</textarea></label>
        <p class="lede" style="font-size:13px;opacity:.75">Tip: use a blank line between paragraphs. The first shows under Work; the second under Contact.</p>
        <label class="field">License #<input name="license_no" value="${esc(s.license_no || "")}" /></label>
        <label class="field">Invoice footer<textarea name="invoice_footer" rows="3">${esc(s.invoice_footer || "")}</textarea></label>
        <button class="btn btn-primary" type="submit">Save website</button>
      </form>
    `);
    $("#wf").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      await api("/settings", { method: "PUT", body });
      toast("Website saved — live on the public site");
    });
  }

  /* ---------------- Web requests ---------------- */
  async function pageRequests() {
    setTitle("Requests");
    const rows = await api("/requests");
    html(`
      <div class="row-between"><h1>Requests</h1></div>
      <p class="lede">Consult requests from the public site. New ones also show on the dashboard.</p>
      <div class="filter-bar" id="rf">
        ${["all", "new", "contacted", "converted", "closed"].map((s) => `<button type="button" data-s="${s}" class="${s === "all" ? "on" : ""}">${s}</button>`).join("")}
      </div>
      <div id="rl">${rows.length ? requestList(rows) : `<div class="empty">No web requests yet.</div>`}</div>
    `);
    $("#rf").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#rf button").forEach((x) => x.classList.toggle("on", x === b));
      const s = b.dataset.s;
      const show = s === "all" ? rows : rows.filter((r) => r.status === s);
      $("#rl").innerHTML = show.length ? requestList(show) : `<div class="empty">None.</div>`;
    });
  }

  async function pageRequest(id) {
    const r = await api("/requests/" + id);
    setTitle(r.name);
    html(`
      <div class="row-between"><h1>${esc(r.name)}</h1>${badge(r.status)}</div>
      <p class="lede">${esc(serviceLabel(r.service))} · ${fmtWhen(r.created_at)}</p>
      <div class="card stack">
        <div><div class="tiny">Phone</div><div class="strong">${esc(r.phone || "—")}</div></div>
        <div><div class="tiny">Email</div><div>${esc(r.email || "—")}</div></div>
        <div><div class="tiny">Address</div><div class="addr">${esc([r.street, [r.city, r.state, r.zip].filter(Boolean).join(" ")].filter(Boolean).join(", ") || "—")}</div></div>
        ${r.preferred ? `<div><div class="tiny">Preferred time</div><div>${esc(r.preferred)}</div></div>` : ""}
        <div><div class="tiny">Message</div><div>${esc(r.message || "—")}</div></div>
      </div>
      <form class="card stack" id="rs" style="margin-top:10px">
        <label class="field">Status
          <select name="status">
            ${["new", "contacted", "converted", "closed"].map((s) => `<option value="${s}" ${r.status === s ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </label>
        <button class="btn btn-primary" type="submit">Save status</button>
      </form>
      <div class="btn-row" style="margin-top:14px">
        ${r.phone ? `<a class="btn btn-ghost" href="${phoneHref(r.phone)}">Call</a>` : ""}
        ${r.email ? `<a class="btn btn-ghost" href="mailto:${esc(r.email)}">Email</a>` : ""}
        ${r.customer_id ? `<a class="btn btn-ghost" href="#/customers/${r.customer_id}">Open customer</a>` : ""}
      </div>
      <button class="btn btn-delete no-print" type="button" id="del-rec">Delete request</button>
    `);
    $("#rs").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      await api("/requests/" + id, { method: "PUT", body });
      toast("Status saved");
      pageRequest(id);
    });
    bindDelete($("#del-rec"), {
      path: "/requests/" + id, kind: "request", name: r.name,
      after: () => { location.hash = "#/requests"; },
    });
  }

  /* ---------------- Router ---------------- */
  async function route() {
    const { path, parts } = parseHash();
    renderNav("/" + (parts[0] || ""));
    $("#sheet").hidden = true;
    if (path === "/more") {
      $("#sheet").hidden = false;
      return;
    }
    try {
      if (!parts.length) return await pageDashboard();
      const [a, b, c] = parts;
      if (a === "requests" && b) return await pageRequest(b);
      if (a === "requests") return await pageRequests();
      if (a === "customers" && b === "new") return await pageCustomer(null, true);
      if (a === "customers" && b) return await pageCustomer(b);
      if (a === "customers") return await pageCustomers();
      if (a === "quotes" && b === "new") return await pageQuote(null, true);
      if (a === "quotes" && b) return await pageQuote(b);
      if (a === "quotes") return await pageQuotes();
      if (a === "jobs" && b === "new") return await pageJob(null, true);
      if (a === "jobs" && b) return await pageJob(b);
      if (a === "jobs") return await pageJobs();
      if (a === "schedule") return await pageSchedule();
      if (a === "invoices" && b && c === "print") return await pageInvoice(b, true);
      if (a === "invoices" && b) return await pageInvoice(b);
      if (a === "invoices") return await pageInvoices();
      if (a === "inventory") return await pageInventory();
      if (a === "team") return await pageTeam();
      if (a === "settings") return await pageSettings();
      if (a === "website") return await pageWebsite();
      html(`<div class="empty">Not found.</div>`);
    } catch (err) {
      html(`<div class="empty">${esc(err.message || err)}</div>`);
    }
  }

  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href='#/more']");
    if (a) {
      e.preventDefault();
      $("#sheet").hidden = false;
    }
  });
  $("#sheet-close").addEventListener("click", () => { $("#sheet").hidden = true; });
  $("#sheet-nav").addEventListener("click", () => { $("#sheet").hidden = true; });

  viewEl = $("#view");
  window.addEventListener("hashchange", route);
  if (!location.hash) location.hash = "#/";
  route();
})();
