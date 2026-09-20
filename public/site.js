(function () {
  const nav = document.getElementById("nav");
  const mark = document.getElementById("nav-mark");
  const overlay = document.getElementById("nav-overlay");
  const toggle = document.getElementById("nav-toggle");
  const hero = document.getElementById("home");

  function onScroll() {
    const light = window.scrollY > (hero ? hero.offsetHeight - 80 : 40);
    nav.classList.toggle("light", light);
    if (mark) mark.src = light ? "/brand/logo-icon.svg" : "/brand/logo-icon-white.svg";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  function closeMenu() { overlay.hidden = true; }
  toggle.addEventListener("click", () => {
    overlay.hidden = !overlay.hidden;
  });
  overlay.addEventListener("click", (e) => {
    if (e.target.closest("a")) closeMenu();
  });

  function setText(id, value) {
    if (!value) return;
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function applyAbout(blurb) {
    if (!blurb) return;
    const parts = String(blurb).split(/\n\n+/).map((s) => s.trim()).filter(Boolean);
    const work = document.getElementById("work-blurb");
    const contact = document.getElementById("contact-about");
    if (parts[0] && work) work.textContent = parts[0];
    if (parts[1] && contact) contact.textContent = parts[1];
    else if (parts[0] && contact && !parts[1]) {
      /* keep contact line if only one paragraph */
    }
  }

  fetch("/api/public/company")
    .then((r) => r.json())
    .then((c) => {
      const phone = document.getElementById("c-phone");
      const email = document.getElementById("c-email");
      const addr = document.getElementById("c-addr");
      const area = document.getElementById("c-area");
      const lic = document.getElementById("c-lic");
      if (c.phone && phone) {
        phone.textContent = c.phone;
        phone.href = "tel:" + String(c.phone).replace(/[^\d+]/g, "");
      }
      if (c.email && email) {
        email.textContent = c.email;
        email.href = "mailto:" + c.email;
      }
      if (addr && (c.street || c.city)) {
        addr.innerHTML = [c.street, [c.city, c.state, c.zip].filter(Boolean).join(" ")].filter(Boolean).join("<br>");
      }
      if (c.service_area && area) area.textContent = c.service_area;
      if (c.license_no && lic) {
        const st = (c.state || "FL").toUpperCase();
        const label = st === "FL" ? "Florida Electrical Contractor License " : "Electrical Contractor License ";
        lic.textContent = label + c.license_no;
      }
      setText("hero-eyebrow", c.location_line);
      setText("hero-headline", c.hero_headline);
      setText("hero-subhead", c.hero_subhead);
      setText("foot-tagline", c.tagline);
      setText("foot-company", c.company_name);
      applyAbout(c.about_blurb);
      if (c.company_name) {
        const meta = document.querySelector('meta[name="description"]');
        if (meta) {
          meta.setAttribute(
            "content",
            c.company_name + " — " + (c.service_area || "Central Florida") + ". " + (c.tagline || "")
          );
        }
        document.title = c.company_name;
      }
      const stateInput = document.querySelector('#consult-form input[name="state"]');
      if (stateInput && c.state) stateInput.value = c.state;
    })
    .catch(() => {});

  const form = document.getElementById("consult-form");
  const ok = document.getElementById("consult-ok");
  const err = document.getElementById("form-err");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.hidden = true;
    const body = Object.fromEntries(new FormData(form).entries());
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      const r = await fetch("/api/public/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Could not send");
      form.hidden = true;
      ok.hidden = false;
      const code = document.getElementById("portal-code");
      if (code) code.textContent = data.portal_code || "—";
    } catch (ex) {
      err.hidden = false;
      err.textContent = ex.message || "Could not send. Please call the office.";
      btn.disabled = false;
    }
  });
})();
