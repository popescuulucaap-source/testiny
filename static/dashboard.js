(() => {
  "use strict";
  const guildId = String(window.GARGAND_GUILD_ID || "");
  if (!guildId) return;
  const api = (path) => "/api/dashboard/" + encodeURIComponent(guildId) + path;
  const readJson = async (response) => {
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.ok === false) throw new Error(data.error || ("Request failed (" + response.status + ")"));
    return data;
  };
  const say = (node, message, bad=false) => {
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("error", !!bad);
    node.classList.toggle("success", !bad);
  };
  const setupTabs = () => {
    const tabs = [...document.querySelectorAll(".side-menu [data-tab]")];
    const panels = [...document.querySelectorAll(".tab-panel")];
    const show = (id) => {
      tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === id));
      panels.forEach(p => p.classList.toggle("active", p.id === id));
    };
    tabs.forEach(t => t.addEventListener("click", () => show(t.dataset.tab)));
    document.querySelectorAll("[data-tab-jump]").forEach(a => a.addEventListener("click", e => {
      e.preventDefault(); show(a.dataset.tabJump);
      document.querySelector(".dashboard-grid")?.scrollIntoView({behavior:"smooth",block:"start"});
    }));
  };
  const loadResources = async () => {
    const selects = [...document.querySelectorAll('select[data-resource]')];
    if (!selects.length) return;
    selects.forEach(s => { s.innerHTML = '<option value="">Loading…</option>'; s.disabled = true; });
    try {
      const data = await readJson(await fetch(api("/resources"), {credentials:"same-origin",headers:{"Accept":"application/json"}}));
      selects.forEach(select => {
        const kind = select.dataset.resource;
        const items = kind === "role" ? (data.roles || []) : (data.channels || []);
        const current = String(select.dataset.current || "");
        const blank = document.createElement("option"); blank.value = ""; blank.textContent = "— Not set —";
        select.replaceChildren(blank);
        items.sort((a,b) => kind === "channel" ? (a.position-b.position || a.name.localeCompare(b.name)) : (b.position-a.position || a.name.localeCompare(b.name)));
        items.forEach(item => {
          const option = document.createElement("option");
          option.value = String(item.id);
          option.textContent = kind === "channel" ? ((item.type === 4 ? "▰ " : "# ") + item.name) : ("@ " + item.name);
          select.appendChild(option);
        });
        select.value = current;
        if (current && select.value !== current) {
          const missing = document.createElement("option"); missing.value=current; missing.textContent="Previously saved selection (not returned by Discord)";
          select.appendChild(missing); select.value=current;
        }
        select.disabled = false;
      });
    } catch (error) {
      selects.forEach(s => { s.disabled = false; s.innerHTML = '<option value="">Could not load options</option>'; });
      const notice = document.querySelector(".bot-connection-card");
      if (notice) say(notice.querySelector("p"), "Could not load Discord channels/roles: " + error.message, true);
    }
  };
  const valueFor = (input) => {
    const key = input.dataset.setting;
    if (input.type === "checkbox") return input.checked;
    if (input.dataset.resource) return input.value || "";
    if (key === "ticket_options") return input.value.split(",").map(x => x.trim()).filter(Boolean);
    if (key === "ticket_questions") {
      try { return JSON.parse(input.value || "{}"); }
      catch (_) { throw new Error("Ticket questions must be valid JSON."); }
    }
    if (input.type === "number") return input.value === "" ? "" : Number(input.value);
    return input.value;
  };
  document.querySelectorAll(".save-settings").forEach(button => button.addEventListener("click", async () => {
    const card = button.closest(".setting-group");
    const notice = card?.querySelector(".save-result");
    const fields = [...(card?.querySelectorAll("[data-setting]") || [])];
    const payload = {};
    try {
      fields.forEach(field => { payload[field.dataset.setting] = valueFor(field); });
      button.disabled = true; button.textContent = "Saving…";
      say(notice, "Sending changes to Gargand…");
      const data = await readJson(await fetch(api("/settings"), {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json","Accept":"application/json"},
        body:JSON.stringify(payload)
      }));
      say(notice, data.queued ? "Saved to the sync queue. Gargand will apply it on the next bridge check." : "Settings updated.");
    } catch (error) { say(notice, error.message, true); }
    finally { button.disabled = false; button.textContent = "Save " + (card?.querySelector("h2")?.textContent || "settings"); }
  }));
  document.querySelectorAll(".bot-action").forEach(button => button.addEventListener("click", async () => {
    if (button.dataset.confirm && !window.confirm(button.dataset.confirm)) return;
    const result = document.getElementById("actionResult");
    const original = button.textContent;
    button.disabled = true; button.textContent = "Working…";
    say(result, "Sending action to Gargand…");
    try {
      const data = await readJson(await fetch(api("/action"), {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json","Accept":"application/json"},
        body:JSON.stringify({action:button.dataset.action})
      }));
      say(result, data.queued ? "Action queued successfully. It should run on the next bot sync." : "Action completed.");
    } catch (error) { say(result, error.message, true); }
    finally { button.disabled = false; button.textContent = original; }
  }));
  setupTabs();
  loadResources();
})();
