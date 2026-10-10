/* GQ Electrical — quote / invoice document layout.
   Header, terms, and footer are LOCKED here (not editable per job).
   Only the customer fields, date/number, scope, and line items vary. */
(function () {
  const LOCKED = {
    company: "GQ ELECTRICAL SERVICES LLC",
    tagline: "Where Guaranteed Meets Quality",
    area: "Orlando / Sanford / Winter Garden",
    phone: "(689) 500-6543",
    email: "Services@gqelectrical.com",
    license: "ER13016834",
  };
  const FOOTER = [
    LOCKED.company, LOCKED.tagline, LOCKED.area, LOCKED.phone, LOCKED.email, "License " + LOCKED.license,
  ].join(" · ");
  const TERMS = [
    "GQ Electrical Services LLC is a Florida Registered Electrical Contractor, license ER13016834, and carries general liability and workers’ compensation insurance.",
    "This quote covers only the work listed in the scope. Anything not listed is not included. The price is good for 30 days.",
    "Payment is due on completion unless this quote states otherwise. Permit fees are charged at the county’s rate, plus the handling amount shown on the quote, and are added to the invoice.",
    "Labor is warranted for one year from completion against defects in workmanship. Materials are covered only by the manufacturer’s warranty.",
    "Any change to the scope must be agreed in writing before the work is done, and may change the price. If we cannot reach the work area, extra time is billed at the crew rate.",
    "This quote is the whole agreement. It is governed by Florida law.",
  ];

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function money(n) {
    if (n === null || n === undefined || n === "") return "";
    return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function field(label, value) {
    return `<div class="gqd-field"><span class="gqd-label">${esc(label)}</span><span class="gqd-val">${esc(value || "")}</span></div>`;
  }

  /* opts: { kind: "quote"|"invoice", number, date, customer:{name,address,cityStateZip,phone,email},
             scope, items:[{description, qty, unit_price}], subtotal, permit, tax, total, paid, balance, minRows } */
  function render(opts) {
    const o = opts || {};
    const isInv = o.kind === "invoice";
    const title = isInv ? "INVOICE" : "QUOTE";
    const c = o.customer || {};
    const items = o.items || [];
    const minRows = o.minRows ?? 8;
    const rows = items.map((it) => `<tr>
        <td>${esc(it.description)}</td>
        <td class="num">${esc(it.qty ?? "")}</td>
        <td class="num">${money(it.unit_price)}</td>
        <td class="num">${it.qty != null && it.unit_price != null ? money(it.qty * it.unit_price) : ""}</td>
      </tr>`);
    while (rows.length < Math.max(minRows, items.length)) rows.push(`<tr class="gqd-blank"><td></td><td></td><td></td><td></td></tr>`);
    const scopeHtml = o.scope
      ? `<div class="gqd-scope">${esc(o.scope).replace(/\n/g, "<br>")}</div>`
      : `<div class="gqd-scope gqd-scope-blank"></div>`;
    const extra = [];
    if (o.tax) extra.push(`<div class="gqd-sum"><span>Tax</span><span>${money(o.tax)}</span></div>`);
    const after = [];
    if (o.paid) {
      after.push(`<div class="gqd-sum"><span>Paid</span><span>${money(o.paid)}</span></div>`);
      after.push(`<div class="gqd-sum gqd-strong"><span>Balance due</span><span>${money(o.balance)}</span></div>`);
    }
    return `<article class="gqdoc">
      <header class="gqd-head">
        <img class="gqd-logo" src="/brand/logo-icon-doc.png" alt="GQ Electrical" />
        <div class="gqd-company">${LOCKED.company}</div>
        <div class="gqd-tagline">${LOCKED.tagline}</div>
        <div class="gqd-contact">${LOCKED.area}</div>
        <div class="gqd-contact">${LOCKED.phone} &nbsp;|&nbsp; ${LOCKED.email}</div>
      </header>
      <div class="gqd-gold"></div>
      <section class="gqd-titlerow">
        ${field("Date", o.date)}
        <div class="gqd-title">${title}</div>
        ${field(title === "QUOTE" ? "Quote #" : "Invoice #", o.number)}
      </section>
      <section class="gqd-parties">
        <div>
          <h3>Contractor</h3>
          <div class="gqd-fixed">GQ Electrical Services LLC</div>
          <div class="gqd-fixed gqd-muted">${LOCKED.area}</div>
          <div class="gqd-fixed gqd-muted">${LOCKED.phone} · ${LOCKED.email}</div>
          <div class="gqd-fixed gqd-muted">License ${LOCKED.license}</div>
        </div>
        <div>
          <h3>Customer</h3>
          ${field("Name", c.name)}
          ${field("Address", c.address)}
          ${field("City, State, ZIP", c.cityStateZip)}
          ${field("Phone", c.phone)}
          ${field("Email", c.email)}
        </div>
      </section>
      <section>
        <h2>1. Scope of Work</h2>
        ${scopeHtml}
      </section>
      <section>
        <h2>2. Price</h2>
        <table class="gqd-table">
          <thead><tr><th>Description</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr></thead>
          <tbody>${rows.join("")}</tbody>
        </table>
        <div class="gqd-sums">
          <div class="gqd-sum"><span>Subtotal</span><span>${money(o.subtotal)}</span></div>
          <div class="gqd-sum"><span>Permit (county fee + handling)</span><span>${money(o.permit)}</span></div>
          ${extra.join("")}
          <div class="gqd-total"><span>${isInv ? "TOTAL DUE" : "TOTAL"}</span><span>${money(o.total)}</span></div>
          ${after.join("")}
        </div>
      </section>
      <section class="gqd-terms">
        <h2>3. TERMS</h2>
        <ul>${TERMS.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
      </section>
      <footer class="gqd-foot">${esc(FOOTER)}</footer>
    </article>`;
  }

  window.GQDoc = { render, LOCKED, TERMS, FOOTER };
})();
