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
  const PRESETS = {
    gaming: {
      xp_enabled:true, analytics_enabled:true, automod_spam:true, automod_flood:true,
      automod_mentions:true, anti_link:false, anti_raid:false, anti_nuke:false,
      raid_auto_lockdown:false, anti_nuke_auto_lockdown:false, anti_nuke_auto_ban:false,
      automod_punishment:"timeout", automod_max_messages:6, automod_window_seconds:5,
      automod_mention_limit:5, ticket_options:["support","report","partnership"]
    },
    security: {
      anti_raid:true, raid_auto_lockdown:true, anti_nuke:true, anti_nuke_auto_lockdown:false,
      anti_nuke_auto_ban:false, anti_link:true, automod_spam:true, automod_flood:true,
      automod_mentions:true, automod_bad_words:false, automod_punishment:"timeout",
      automod_max_messages:5, automod_window_seconds:5, automod_mention_limit:4
    },
    creator: {
      xp_enabled:true, analytics_enabled:true, anti_raid:false, anti_nuke:false,
      anti_link:false, automod_spam:true, automod_flood:true, automod_mentions:true,
      ticket_options:["support","report","partnership","creator"], ticket_questions:{
        support:["How can we help?"], report:["Who or what are you reporting?","Please share details."],
        partnership:["Tell us about your community or project."], creator:["Share your channel or creator profile."]
      }
    }
  };
  const applyPresetToFields = (preset) => {
    const payload = PRESETS[preset];
    if (!payload) return;
    const notice = document.getElementById("presetApplyResult");
    const button = document.querySelector('.apply-preset[data-preset="' + preset + '"]');
    const card = button?.closest(".preset-card");
    const original = button?.textContent || "Apply preset";
    if (button) { button.disabled = true; button.textContent = "Applying…"; }
    if (notice) { notice.textContent = "Sending preset to Gargand…"; notice.classList.remove("error","success"); }
    Object.entries(payload).forEach(([key,value]) => {
      const field = document.querySelector('[data-setting="' + key + '"]');
      if (!field) return;
      if (field.type === "checkbox") field.checked = !!value;
      else if (field.dataset.resource === "roles") {
        const chosen = Array.isArray(value) ? value.map(String) : [];
        [...field.options].forEach(option => option.selected = chosen.includes(option.value));
      } else if (key === "ticket_options") field.value = Array.isArray(value) ? value.join(", ") : value;
      else if (key === "ticket_questions") field.value = JSON.stringify(value, null, 2);
      else field.value = value;
    });
    fetch(api("/settings"), {
      method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify(payload)
    }).then(readJson).then(data => {
      if (notice) {
        notice.textContent = data.queued
          ? "Preset queued! Gargand will apply it on its next bridge sync. Now choose the relevant channels and roles in the tabs, then save those settings."
          : "Preset applied. Review your channels and roles before finishing setup.";
        notice.classList.add("success");
      }
    }).catch(error => {
      if (notice) { notice.textContent = "Preset could not be applied: " + (error.message || "Unknown error"); notice.classList.add("error"); }
    }).finally(() => {
      if (button) { button.disabled = false; button.textContent = original; }
    });
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
        const multipleRoles = kind === "roles";
        const items = (kind === "role" || multipleRoles) ? (data.roles || []) : (data.channels || []);
        let current = select.dataset.current || "";
        if (multipleRoles) {
          try { current = JSON.parse(current || "[]"); } catch (_) { current = []; }
          if (!Array.isArray(current)) current = [];
          current = current.map(String);
        } else current = String(current);
        const blank = document.createElement("option"); blank.value = ""; blank.textContent = "— Not set —";
        select.replaceChildren(blank);
        if (multipleRoles) select.removeChild(blank);
        items.sort((a,b) => kind === "channel" ? (a.position-b.position || a.name.localeCompare(b.name)) : (b.position-a.position || a.name.localeCompare(b.name)));
        items.forEach(item => {
          const option = document.createElement("option");
          option.value = String(item.id);
          option.textContent = kind === "channel" ? ((item.type === 4 ? "▰ " : "# ") + item.name) : ("@ " + item.name);
          if (multipleRoles) option.selected = current.includes(option.value);
          select.appendChild(option);
        });
        if (multipleRoles) {
          current.filter(id => !items.some(item => String(item.id) === id)).forEach(id => {
            const missing = document.createElement("option"); missing.value=id; missing.textContent="Saved role unavailable · "+id; missing.selected=true; select.appendChild(missing);
          });
        } else {
          select.value = current;
          if (current && select.value !== current) {
            const missing = document.createElement("option"); missing.value=current; missing.textContent="Previously saved selection (not returned by Discord)";
            select.appendChild(missing); select.value=current;
          }
        }
        select.disabled = false;
      });
    } catch (error) {
      const message = "Could not load options: " + (error.message || "Discord resource request failed.");
      selects.forEach(select => {
        select.disabled = false;
        select.replaceChildren();
        const option = document.createElement("option");
        option.value = "";
        option.textContent = message;
        select.appendChild(option);
        select.title = message;
      });
      let notice = document.getElementById("dashboardResourceError");
      if (!notice) {
        notice = document.createElement("p");
        notice.id = "dashboardResourceError";
        notice.className = "notice error";
        notice.setAttribute("role", "status");
        const host = document.querySelector(".dashboard-content");
        if (host) host.prepend(notice);
      }
      if (notice) notice.textContent = "Discord channels and roles could not be loaded. " + (error.message || "Refresh after Gargand checks in.");
    }
  };
  const valueFor = (input) => {
    const key = input.dataset.setting;
    if (input.type === "checkbox") return input.checked;
    if (input.dataset.resource === "roles") return [...input.selectedOptions].map(option => option.value).filter(Boolean);
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
  document.querySelectorAll(".apply-preset").forEach(button => button.addEventListener("click", () => applyPresetToFields(button.dataset.preset)));
  setupTabs();
  loadResources();
})();
