(function () {
  const root = document.getElementById("root");
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
    return new Date(+y, +m - 1, +day).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  const params = new URLSearchParams(location.search);
  const pathId = location.pathname.replace(/^\/pay\/?/, "");
  const key = params.get("n") || params.get("id") || pathId || "";

  if (!key) {
    root.innerHTML = `<p>Missing invoice. Open a pay link from your portal, or <a href="/portal">sign in</a>.</p>`;
    return;
  }

  async function load() {
    const r = await fetch("/api/public/invoices/" + encodeURIComponent(key));
    const inv = await r.json();
    if (!r.ok) throw new Error(inv.error || "Invoice not found");
    return inv;
  }

  function receipt(inv) {
    document.getElementById("pay-title").textContent = inv.number + " paid";
    document.getElementById("pay-sub").textContent = "Thank you. The shop has the payment on file.";
    root.innerHTML = `
      <div class="ok-screen">
        <p class="eyebrow">Payment recorded</p>
        <h2>Settled.</h2>
        <p class="meta">${esc(inv.customer?.name || "")} · ${esc(inv.number)}</p>
        <p class="pay-summary grand" style="margin:18px 0">${money(inv.paid)} received</p>
        ${(inv.payments || []).map((p) => `<div class="doc"><div class="meta">${esc(p.method)} · ${esc(p.reference || "")}</div><div class="amt">${money(p.amount)}</div></div>`).join("")}
        <p style="margin-top:28px"><a class="btn-line" href="/portal">Back to portal</a></p>
      </div>`;
  }

  function checkout(inv) {
    document.getElementById("pay-title").textContent = "Pay " + inv.number;
    const co = inv.company || {};
    root.innerHTML = `
      <div class="pay-summary">
        <p class="eyebrow">${esc(co.company_name || "GQ Electrical Services")}</p>
        <div class="row-between"><span>${esc(inv.customer?.name || "")}</span><span class="pill">${esc(inv.status)}</span></div>
        <div class="meta">Due ${fmtDate(inv.due_date)}</div>
        <div class="grand">${money(inv.balance)} due</div>
        <div class="meta">Invoice total ${money(inv.total)} · already paid ${money(inv.paid)}</div>
      </div>
      <table class="line-table">
        <thead><tr><th>Description</th><th class="num">Amt</th></tr></thead>
        <tbody>
          ${(inv.items || []).map((it) => `<tr><td>${esc(it.description)}</td><td class="num">${money(it.qty * it.unit_price)}</td></tr>`).join("")}
        </tbody>
      </table>
      <form class="form" id="cf" style="margin-top:32px">
        <label class="field">Amount
          <input name="amount" type="number" min="0.01" step="0.01" value="${inv.balance.toFixed(2)}" required />
        </label>
        <label class="field">Name on card
          <input name="cardholder" autocomplete="cc-name" required />
        </label>
        <label class="field">Card number
          <input name="card_number" inputmode="numeric" autocomplete="cc-number" placeholder="•••• •••• •••• ••••" required />
        </label>
        <div class="card-row">
          <label class="field">Expiry
            <input name="exp" placeholder="MM / YY" autocomplete="cc-exp" required />
          </label>
          <label class="field">CVC
            <input name="cvc" inputmode="numeric" autocomplete="cc-csc" maxlength="4" required />
          </label>
        </div>
        <p class="notice">This checkout records the payment in GQ’s books. It does not send the card to a processor. Stripe can be connected later.</p>
        <p class="err" id="err" hidden></p>
        <button class="btn-dark" type="submit">Pay ${money(inv.balance)}</button>
      </form>
    `;
    const form = document.getElementById("cf");
    const num = form.querySelector("[name=card_number]");
    num.addEventListener("input", () => {
      const d = num.value.replace(/\D/g, "").slice(0, 19);
      num.value = d.replace(/(\d{4})(?=\d)/g, "$1 ").trim();
    });
    const amt = form.querySelector("[name=amount]");
    const btn = form.querySelector("button[type=submit]");
    amt.addEventListener("input", () => {
      const n = Number(amt.value) || 0;
      btn.textContent = "Pay " + money(n);
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = document.getElementById("err");
      err.hidden = true;
      const fd = new FormData(form);
      const pan = String(fd.get("card_number") || "").replace(/\D/g, "");
      if (pan.length < 13 || pan.length > 19) {
        err.hidden = false;
        err.textContent = "Enter a complete card number.";
        return;
      }
      btn.disabled = true;
      try {
        const r = await fetch("/api/public/invoices/" + encodeURIComponent(inv.id) + "/pay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            amount: Number(fd.get("amount")),
            card_number: pan,
            cardholder: fd.get("cardholder"),
          }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Payment failed");
        receipt(data);
      } catch (ex) {
        err.hidden = false;
        err.textContent = ex.message;
        btn.disabled = false;
      }
    });
  }

  load()
    .then((inv) => {
      if (inv.balance <= 0) receipt(inv);
      else checkout(inv);
    })
    .catch((e) => {
      root.innerHTML = `<p>${esc(e.message)}</p><p class="form-note"><a href="/portal">Return to portal</a></p>`;
    });
})();
