(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const h = (tag, props = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  };

  async function api(method, path, body) {
    const r = await fetch(path, {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (r.status === 401 && path !== "/api/login") { showLogin(); throw new Error("Please log in again."); }
    if (!r.ok) throw new Error(data.error || "Something went wrong.");
    return data;
  }

  let flashTimer;
  function flash(text, kind = "ok") {
    const el = $("#flash");
    el.textContent = text;
    el.className = `msg ${kind}`;
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => el.classList.add("hidden"), 5000);
  }

  // ------------------------------------------------------------ views
  let me = {};
  function showLogin(note) {
    $("#appView").classList.add("hidden");
    $("#loginView").classList.remove("hidden");
    const m = $("#loginMsg");
    if (note) { m.textContent = note; m.classList.remove("hidden"); } else m.classList.add("hidden");
  }
  async function showApp() {
    $("#loginView").classList.add("hidden");
    $("#appView").classList.remove("hidden");
    const n = $("#notices");
    n.replaceChildren();
    if (!me.persistent) n.append(h("div", { class: "msg warn" }, "Storage warning: DATABASE_URL isn't set, so on Render's free plan your announcements will disappear when the site restarts. See the setup steps to add a free database."));
    $("#discordLabel").classList.toggle("hidden", !me.webhook);
    await Promise.all([loadAnnouncements(), loadCommands(), loadSettings()]);
  }

  async function boot() {
    me = await fetch("/api/me").then((r) => r.json());
    if (!me.configured) return showLogin("Admin is turned off. Add an ADMIN_PASSWORD environment variable on Render, then redeploy.");
    if (me.admin) showApp(); else showLogin();
  }

  $("#loginBtn").addEventListener("click", login);
  $("#pw").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
  async function login() {
    try {
      await api("POST", "/api/login", { password: $("#pw").value });
      $("#pw").value = "";
      me = await fetch("/api/me").then((r) => r.json());
      showApp();
    } catch (e) { showLogin(e.message); }
  }
  $("#logoutBtn").addEventListener("click", async () => { await api("POST", "/api/logout"); location.reload(); });

  document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("[data-tab]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    for (const t of ["ann", "cmd", "set"]) $(`#tab-${t}`).classList.toggle("hidden", t !== b.dataset.tab);
  }));

  // ---------------------------------------------------- announcements
  let editing = null;
  const TAGS = { new: "🆕 New", update: "🔧 Update", fix: "🐛 Fix", maintenance: "⚠️ Maintenance", news: "📣 News" };
  $("#aBody").addEventListener("input", () => { $("#aCount").textContent = `(${$("#aBody").value.length}/4000)`; });

  function resetForm() {
    editing = null;
    $("#aTitle").value = ""; $("#aBody").value = ""; $("#aTag").value = "update";
    $("#aPinned").checked = false; $("#aDiscord").checked = false; $("#aCount").textContent = "";
    $("#annHeading").textContent = "New announcement";
    $("#aSave").textContent = "Post announcement";
    $("#aCancel").classList.add("hidden");
  }
  $("#aCancel").addEventListener("click", resetForm);

  async function loadAnnouncements() {
    const { announcements } = await fetch("/api/site").then((r) => r.json());
    const box = $("#annList");
    box.replaceChildren();
    if (!announcements.length) box.append(h("p", { class: "muted" }, "No announcements yet."));
    [...announcements].sort((a, b) => (b.pinned - a.pinned) || (b.date - a.date)).forEach((a) => {
      box.append(h("div", { class: "item" },
        h("div", {}, h("b", {}, (a.pinned ? "📌 " : "") + a.title), h("small", {}, `${TAGS[a.tag] || ""} · ${new Date(a.date).toLocaleString()}`)),
        h("div", { class: "acts" },
          h("button", { class: "btn small ghost", type: "button", onclick: () => {
            editing = a.id;
            $("#aTitle").value = a.title; $("#aBody").value = a.body; $("#aTag").value = a.tag; $("#aPinned").checked = a.pinned;
            $("#annHeading").textContent = "Edit announcement";
            $("#aSave").textContent = "Save changes";
            $("#aCancel").classList.remove("hidden");
            scrollTo({ top: 0, behavior: "smooth" });
          } }, "Edit"),
          h("button", { class: "btn small danger", type: "button", onclick: async () => {
            if (!confirm(`Delete "${a.title}"?`)) return;
            try { await api("DELETE", `/api/announcements/${a.id}`); flash("Deleted."); loadAnnouncements(); } catch (e) { flash(e.message, "err"); }
          } }, "Delete"))));
    });
  }

  $("#aSave").addEventListener("click", async () => {
    const payload = { title: $("#aTitle").value, body: $("#aBody").value, tag: $("#aTag").value, pinned: $("#aPinned").checked, discord: $("#aDiscord").checked };
    try {
      if (editing) { await api("PUT", `/api/announcements/${editing}`, payload); flash("Changes saved."); }
      else {
        const r = await api("POST", "/api/announcements", payload);
        flash(r.discord === true ? "Posted on the website and in Discord." : r.discord === false ? "Posted on the website, but the Discord post failed." : "Posted on the website.", r.discord === false ? "warn" : "ok");
      }
      resetForm();
      loadAnnouncements();
    } catch (e) { flash(e.message, "err"); }
  });

  // ---------------------------------------------------------- commands
  let cmds = [];
  function renderCommandRows() {
    const cats = [...new Set(cmds.map((c) => c.category))];
    $("#cats").replaceChildren(...cats.map((c) => h("option", { value: c })));
    const box = $("#cmdRows");
    box.replaceChildren();
    cmds.forEach((c, i) => {
      const bind = (field, el) => { el.addEventListener("input", () => { cmds[i][field] = el.type === "checkbox" ? el.checked : el.value; }); return el; };
      const check = (field, label) => h("label", {}, bind(field, Object.assign(h("input", { type: "checkbox" }), { checked: c[field] })), label);
      box.append(h("div", { class: "row-in" },
        bind("name", h("input", { value: c.name, placeholder: "name", "aria-label": "Command name", maxlength: 40 })),
        bind("category", h("input", { value: c.category, list: "cats", placeholder: "category", "aria-label": "Category", maxlength: 30 })),
        bind("usage", h("input", { value: c.usage, placeholder: "usage", "aria-label": "Usage", maxlength: 120 })),
        bind("description", h("input", { value: c.description, placeholder: "what it does", "aria-label": "Description", maxlength: 300 })),
        check("staff", "Staff"), check("prefixOnly", "Prefix only"),
        h("button", { class: "btn small danger", type: "button", "aria-label": "Remove command", onclick: () => { cmds.splice(i, 1); renderCommandRows(); } }, "✕")));
    });
  }
  async function loadCommands() {
    cmds = (await fetch("/api/site").then((r) => r.json())).commands;
    renderCommandRows();
  }
  $("#cAdd").addEventListener("click", () => {
    cmds.push({ name: "", category: cmds.length ? cmds[cmds.length - 1].category : "Utility", usage: "", description: "", staff: false, prefixOnly: false });
    renderCommandRows();
    document.querySelector("#cmdRows .row-in:last-child input")?.focus();
  });
  $("#cSave").addEventListener("click", async () => {
    try { const r = await api("PUT", "/api/commands", { commands: cmds }); cmds = r.commands; renderCommandRows(); flash("Commands saved."); } catch (e) { flash(e.message, "err"); }
  });
  $("#cReset").addEventListener("click", async () => {
    if (!confirm("Replace your command list with the default one?")) return;
    try { const r = await api("POST", "/api/commands/reset", {}); cmds = r.commands; renderCommandRows(); flash("Reset to defaults."); } catch (e) { flash(e.message, "err"); }
  });

  // ---------------------------------------------------------- settings
  async function loadSettings() {
    const { settings } = await fetch("/api/site").then((r) => r.json());
    $("#sInvite").value = settings.invite; $("#sSupport").value = settings.support;
  }
  $("#sSave").addEventListener("click", async () => {
    try {
      const r = await api("PUT", "/api/settings", { invite: $("#sInvite").value, support: $("#sSupport").value });
      $("#sInvite").value = r.settings.invite; $("#sSupport").value = r.settings.support;
      flash("Settings saved. Links must start with https://");
    } catch (e) { flash(e.message, "err"); }
  });

  boot();
})();
