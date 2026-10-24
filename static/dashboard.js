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
      automod_mentions:true, automod_punishment:"timeout", automod_max_messages:6, automod_window_seconds:5,
      automod_mention_limit:5, ticket_options:["support","report","partnership"]
    },
    security: {
      anti_raid:true, raid_auto_lockdown:true, anti_nuke:true, anti_nuke_auto_lockdown:false,
      anti_nuke_auto_ban:false, anti_link:true, automod_spam:true, automod_flood:true,
      automod_mentions:true, automod_bad_words:false, automod_punishment:"timeout",
      automod_max_messages:5, automod_window_seconds:5, automod_mention_limit:4
    },
    creator: {
      xp_enabled:true, analytics_enabled:true, automod_spam:true, automod_flood:true, automod_mentions:true,
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
        let items = (kind === "role" || multipleRoles) ? (data.roles || []) : (data.channels || []);
        if (kind === "voice-channel") items = items.filter(item => Number(item.type) === 2);
        if (kind === "text-channel") items = items.filter(item => [0, 5].includes(Number(item.type)));
        let current = select.dataset.current || "";
        if (multipleRoles) {
          try { current = JSON.parse(current || "[]"); } catch (_) { current = []; }
          if (!Array.isArray(current)) current = [];
          current = current.map(String);
        } else current = String(current);
        const blank = document.createElement("option"); blank.value = ""; blank.textContent = "— Not set —";
        select.replaceChildren(blank);
        if (multipleRoles) select.removeChild(blank);
        items.sort((a,b) => (kind === "channel" || kind === "voice-channel" || kind === "text-channel") ? (a.position-b.position || a.name.localeCompare(b.name)) : (b.position-a.position || a.name.localeCompare(b.name)));
        items.forEach(item => {
          const option = document.createElement("option");
          option.value = String(item.id);
          option.textContent = (kind === "channel" || kind === "voice-channel" || kind === "text-channel") ? ((Number(item.type) === 2 ? "♫ " : Number(item.type) === 4 ? "▰ " : "# ") + item.name) : ("@ " + item.name);
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
  const formatDuration = seconds => {
    const value = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(value / 60);
    const remainder = Math.floor(value % 60);
    const hours = Math.floor(minutes / 60);
    return hours ? (hours + ":" + String(minutes % 60).padStart(2, "0") + ":" + String(remainder).padStart(2, "0"))
      : (minutes + ":" + String(remainder).padStart(2, "0"));
  };
  const makeNode = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };
  const setListMessage = (node, message) => {
    if (!node) return;
    node.replaceChildren(makeNode("p", "muted", message));
  };
  const appendLiveRow = (container, headingText, detailText, actionButton) => {
    const row = makeNode("article", "dashboard-live-row");
    const copy = makeNode("div", "dashboard-live-copy");
    copy.appendChild(makeNode("strong", "", headingText));
    if (detailText) copy.appendChild(makeNode("p", "", detailText));
    row.appendChild(copy);
    if (actionButton) row.appendChild(actionButton);
    container.appendChild(row);
  };
  const formatTimestamp = value => {
    if (value === undefined || value === null || value === "") return "Time unavailable";
    let date;
    if (typeof value === "number" || /^\d{9,11}$/.test(String(value))) {
      const number = Number(value);
      date = new Date(number < 100000000000 ? number * 1000 : number);
    } else date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  };
  const postDashboardAction = async (action, extras, resultNode) => {
    const data = await readJson(await fetch(api("/action"), {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type":"application/json","Accept":"application/json"},
      body: JSON.stringify(Object.assign({action}, extras || {}))
    }));
    say(resultNode, "Queued successfully. Gargand will process this on its next bridge check.", false);
    return data;
  };

  const musicStateNode = document.getElementById("musicConnectionState");
  const musicTitleNode = document.getElementById("musicCurrentTitle");
  const musicCountNode = document.getElementById("musicQueueCount");
  const musicQueueNode = document.getElementById("musicQueueList");
  const musicVolumeNode = document.getElementById("musicVolume");
  const musicVolumeValue = document.getElementById("musicVolumeValue");
  const musicResult = document.getElementById("musicActionResult");
  const refreshMusic = async () => {
    if (!musicStateNode) return;
    try {
      const data = await readJson(await fetch(api("/music"), {credentials:"same-origin",headers:{"Accept":"application/json"}}));
      const music = data.music || {};
      musicStateNode.textContent = music.connected ? ("Connected · " + (music.channel_name || "voice channel")) : "Not connected";
      const current = music.current || null;
      musicTitleNode.textContent = current ? ((music.paused ? "Paused · " : music.playing ? "Playing · " : "Queued · ") + current.title) : "Nothing playing";
      musicCountNode.textContent = (Number(music.queue_count) || 0) + " queued";
      if (musicVolumeNode && document.activeElement !== musicVolumeNode) musicVolumeNode.value = String(Math.min(150,Math.max(5,Number(music.volume)||50)));
      if (musicVolumeValue) musicVolumeValue.textContent = (musicVolumeNode ? musicVolumeNode.value : (music.volume || 50)) + "%";
      if (musicQueueNode) {
        musicQueueNode.replaceChildren();
        if (current) appendLiveRow(musicQueueNode, "Now playing · " + current.title, formatDuration(current.duration) + (current.requested_by && current.requested_by !== "website" ? " · Requested by " + current.requested_by : ""));
        const queue = Array.isArray(music.queue) ? music.queue : [];
        queue.forEach((track,index) => {
          const row = makeNode("article","dashboard-live-row");
          const copy = makeNode("div","dashboard-live-copy");
          copy.appendChild(makeNode("strong","",((index+1)+". "+track.title)));
          copy.appendChild(makeNode("p","",formatDuration(track.duration)));
          row.appendChild(copy);
          musicQueueNode.appendChild(row);
        });
        if (!current && !queue.length) setListMessage(musicQueueNode,"The queue is empty. Select a voice channel and add a track above.");
      }
    } catch (error) {
      if (musicStateNode) musicStateNode.textContent = "Status unavailable";
      setListMessage(musicQueueNode, error.message || "Could not load music status.");
    }
  };
  if (musicVolumeNode) musicVolumeNode.addEventListener("input", () => {
    if (musicVolumeValue) musicVolumeValue.textContent = musicVolumeNode.value + "%";
  });
  document.querySelectorAll(".music-action").forEach(button => button.addEventListener("click", async () => {
    const action = button.dataset.musicAction;
    const extras = {};
    const voiceSelect = document.getElementById("musicVoiceChannel");
    if (action === "music_join" || action === "music_play") {
      extras.channel_id = voiceSelect ? voiceSelect.value : "";
      if (!extras.channel_id) { say(musicResult,"Choose a voice channel first.",true); return; }
    }
    if (action === "music_play") {
      extras.query = (document.getElementById("musicQuery")?.value || "").trim();
      if (!extras.query) { say(musicResult,"Enter a track title or URL first.",true); return; }
    }
    if (action === "music_volume") extras.volume = Number(musicVolumeNode?.value || 50);
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Sending…";
    try {
      await postDashboardAction(action, extras, musicResult);
      if (action === "music_play") document.getElementById("musicQuery").value = "";
      window.setTimeout(refreshMusic, 1200);
    } catch (error) { say(musicResult,error.message || "Music action failed.",true); }
    finally { button.disabled = false; button.textContent = original; }
  }));

  const communityMetrics = document.getElementById("communityMetrics");
  const communityAnalytics = document.getElementById("communityAnalytics");
  const communityMessage = document.getElementById("communityStateMessage");
  const refreshCommunity = async () => {
    if (!communityMetrics) return;
    try {
      const data = await readJson(await fetch(api("/community"), {credentials:"same-origin",headers:{"Accept":"application/json"}}));
      const stats = data.community || {};
      communityMetrics.replaceChildren();
      [
        ["Members with XP",Number(stats.members_with_xp)||0],
        ["Total XP",Number(stats.total_xp)||0],
        ["Messages tracked",Number(stats.total_messages)||0],
        ["Achievements earned",Number(stats.achievements_earned)||0],
        ["Quests completed today",Number(stats.quests_completed_today)||0],
        ["Monthly season points",Number(stats.season_points)||0],
        ["Co-op parties",Number(stats.party_count)||0]
      ].forEach(([label,value]) => {
        const card = makeNode("div","dashboard-mini-metric");
        card.appendChild(makeNode("small","",label));
        card.appendChild(makeNode("strong","",value.toLocaleString()));
        communityMetrics.appendChild(card);
      });
      if (communityAnalytics) {
        communityAnalytics.replaceChildren();
        (Array.isArray(stats.analytics) ? stats.analytics : []).forEach(item => appendLiveRow(communityAnalytics,String(item.metric || "Activity"),String(Number(item.total)||0)+" events"));
        if (!(stats.analytics || []).length) setListMessage(communityAnalytics,"Analytics are empty or not enabled yet.");
      }
      say(communityMessage, "XP is " + (stats.xp_enabled ? "enabled" : "disabled") + "; analytics are " + (stats.analytics_enabled ? "enabled" : "disabled") + ".", false);
    } catch (error) { say(communityMessage,error.message || "Could not load community snapshot.",true); }
  };

  const securityChecks = document.getElementById("securityPermissionChecks");
  const securityTimeline = document.getElementById("securityTimeline");
  const securityMessage = document.getElementById("securityStateMessage");
  const renderSecurity = async () => {
    if (!securityChecks) return;
    try {
      const data = await readJson(await fetch(api("/security"), {credentials:"same-origin",headers:{"Accept":"application/json"}}));
      const health = data.health || {};
      const settings = data.settings || {};
      securityChecks.replaceChildren();
      const checks = [];
      const permissionMap = health.permissions && typeof health.permissions === "object" ? health.permissions : {};
      Object.entries(permissionMap).forEach(([key,value]) => {
        if (typeof value === "boolean") checks.push([key.replace(/_/g," "),value ? "Available" : "Missing",value]);
        else if (value && typeof value === "object" && ("available" in value || "can_view" in value || "can_send" in value)) {
          const allowed = Boolean(value.available ?? value.can_view ?? value.can_send);
          checks.push([key.replace(/_/g," "), allowed ? "Available" : "Needs attention", allowed]);
        }
      });
      checks.push(["Anti-raid",settings.anti_raid ? "Enabled" : "Disabled",!!settings.anti_raid]);
      checks.push(["Anti-nuke",settings.anti_nuke ? "Enabled" : "Disabled",!!settings.anti_nuke]);
      checks.push(["Anti-link",settings.anti_link ? "Enabled" : "Disabled",!!settings.anti_link]);
      checks.push(["Auto-Mod spam",settings.automod_spam ? "Enabled" : "Disabled",!!settings.automod_spam]);
      if (!checks.length) checks.push(["Bot health snapshot","No permission details were included in the latest heartbeat",false]);
      checks.slice(0,18).forEach(([label,state,ok]) => {
        const card = makeNode("div","security-check-card "+(ok ? "pass" : "attention"));
        card.appendChild(makeNode("span","security-check-indicator",ok ? "✓" : "!"));
        const copy = makeNode("div","");
        copy.appendChild(makeNode("strong","",label));
        copy.appendChild(makeNode("small","",state));
        card.appendChild(copy);
        securityChecks.appendChild(card);
      });
      if (securityTimeline) {
        securityTimeline.replaceChildren();
        (Array.isArray(data.events) ? data.events : []).forEach(event => {
          const meta = event.metadata || {};
          const what = event.command || meta.action || meta.case_id || event.type || "Activity";
          const who = event.username || (event.user_id ? ("User "+event.user_id) : "Gargand");
          const details = Object.keys(meta).length ? Object.entries(meta).map(([k,v]) => k.replace(/_/g," ")+": "+(Array.isArray(v)?v.join(", "):String(v))).join(" · ") : "";
          const row = makeNode("article","dashboard-live-row");
          const copy = makeNode("div","dashboard-live-copy");
          copy.appendChild(makeNode("strong","",what));
          copy.appendChild(makeNode("p","",who+" · "+String(event.type || "event").replace(/_/g," ")+(details ? " · "+details : "")));
          row.appendChild(copy);
          row.appendChild(makeNode("time","dashboard-live-time",formatTimestamp(event.created_at)));
          securityTimeline.appendChild(row);
        });
        if (!data.events || !data.events.length) setListMessage(securityTimeline,data.history_message || "No recent security or staff events were returned.");
      }
      say(securityMessage,data.history_message || "Showing the latest bot permission snapshot and recent activity.",false);
    } catch (error) { say(securityMessage,error.message || "Could not load security status.",true); }
  };
  document.getElementById("refreshSecurityTimeline")?.addEventListener("click",renderSecurity);

  const notificationMessage = document.getElementById("notificationActionResult");
  const rssList = document.getElementById("rssSubscriptionList");
  const animeList = document.getElementById("animeWatchList");
  const refreshNotifications = async () => {
    if (!rssList && !animeList) return;
    try {
      const data = await readJson(await fetch(api("/notifications"), {credentials:"same-origin",headers:{"Accept":"application/json"}}));
      const notifications = data.notifications || {};
      if (rssList) {
        rssList.replaceChildren();
        (Array.isArray(notifications.rss) ? notifications.rss : []).forEach(item => {
          const remove = makeNode("button","btn ghost","Remove");
          remove.type = "button";
          remove.addEventListener("click",async () => {
            remove.disabled = true;
            try {
              await postDashboardAction("notification_rss_remove",{subscription_id:item.id},notificationMessage);
              window.setTimeout(refreshNotifications,1200);
            } catch(error) { say(notificationMessage,error.message || "Could not remove feed.",true); remove.disabled=false; }
          });
          appendLiveRow(rssList,"Subscription #"+item.id,"Channel "+(item.channel_id || "not set")+" · "+item.url,remove);
        });
        if (!(notifications.rss || []).length) setListMessage(rssList,"No RSS feeds are configured.");
      }
      if (animeList) {
        animeList.replaceChildren();
        (Array.isArray(notifications.anime) ? notifications.anime : []).forEach(item => {
          const remove = makeNode("button","btn ghost","Stop alerts");
          remove.type = "button";
          remove.addEventListener("click",async () => {
            remove.disabled = true;
            try {
              await postDashboardAction("notification_anime_remove",{anilist_id:item.anilist_id},notificationMessage);
              window.setTimeout(refreshNotifications,1200);
            } catch(error) { say(notificationMessage,error.message || "Could not remove anime alert.",true); remove.disabled=false; }
          });
          const next = item.next_episode ? (" · Next episode "+item.next_episode) : "";
          appendLiveRow(animeList,item.title+" · AniList "+item.anilist_id,"Channel "+item.channel_id+next,remove);
        });
        if (!(notifications.anime || []).length) setListMessage(animeList,"No anime alerts are configured.");
      }
    } catch (error) {
      setListMessage(rssList,error.message || "Could not load RSS subscriptions.");
      setListMessage(animeList,error.message || "Could not load anime alerts.");
    }
  };
  document.querySelectorAll(".notification-action").forEach(button => button.addEventListener("click",async () => {
    const action = button.dataset.notificationAction;
    const channel = document.getElementById("notificationChannel");
    const extras = {};
    if (!channel || !channel.value) { say(notificationMessage,"Choose a destination text channel first.",true); return; }
    extras.channel_id = channel.value;
    if (action === "notification_rss_add") {
      extras.feed_url = (document.getElementById("notificationFeedUrl")?.value || "").trim();
      if (!extras.feed_url) { say(notificationMessage,"Enter an RSS or Atom feed URL first.",true); return; }
    }
    if (action === "notification_anime_add") {
      extras.anilist_id = Number(document.getElementById("animeListId")?.value || 0);
      if (!extras.anilist_id) { say(notificationMessage,"Enter the AniList anime ID first.",true); return; }
    }
    const original = button.textContent;
    button.disabled = true; button.textContent = "Sending…";
    try {
      await postDashboardAction(action,extras,notificationMessage);
      if (action === "notification_rss_add") document.getElementById("notificationFeedUrl").value = "";
      if (action === "notification_anime_add") document.getElementById("animeListId").value = "";
      window.setTimeout(refreshNotifications,1200);
    } catch(error) { say(notificationMessage,error.message || "Notification action failed.",true); }
    finally { button.disabled=false; button.textContent=original; }
  }));
  document.getElementById("refreshNotifications")?.addEventListener("click",refreshNotifications);

  document.querySelectorAll(".apply-preset").forEach(button => button.addEventListener("click", () => applyPresetToFields(button.dataset.preset)));
  setupTabs();
  loadResources();
  refreshMusic();
  refreshCommunity();
  renderSecurity();
  refreshNotifications();
  window.setInterval(refreshMusic, 12000);
  window.setInterval(refreshCommunity, 20000);
  window.setInterval(renderSecurity, 20000);
  window.setInterval(refreshNotifications, 20000);
})();
