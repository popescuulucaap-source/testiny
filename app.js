(() => {
  "use strict";
  document.documentElement.classList.add("js");
  const $ = (s, el = document) => el.querySelector(s);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Small helper to build elements safely (text is never treated as HTML)
  const h = (tag, props = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    return el;
  };

  const FEATURES = [
    ["Tickets", "A clean panel with buttons, question forms, claim and close buttons, and transcripts."],
    ["Welcome and goodbye cards", "Animated cards with the member's avatar and who invited them."],
    ["Invite tracking", "Real, fake, left, rejoined and J4J invites, counted separately."],
    ["Anti raid and anti nuke", "Bans @everyone spammers and mass channel deleters, then locks things down."],
    ["Anti link", "Times out link senders, but lets GIFs through."],
    ["Verification", "New members solve an image code in a private popup to get in."],
    ["J4J protection", "Asks new members if they joined for a join-for-join, and bans after one hour of silence."],
    ["Jail system", "Take a member's roles and lock them in one channel until staff release them."],
    ["Vouch and feedback", "A vouch channel with embeds, and star-rated feedback from your members."],
    ["Giveaways", "Timers, multiple winners, prize photos, end and reroll."],
    ["Games and coins", "Daily coins, coinflip, high-low, blackjack and roulette, all animated."],
    ["Staff applications", "A ready-made form. Pick the channel and you're done. Boosters get shout-outs too."],
  ];

  // ---------------------------------------------------------- helpers
  let toastTimer;
  function toast(text) {
    const t = $("#toast");
    t.textContent = text;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2000);
  }

  const io = "IntersectionObserver" in window
    ? new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 })
    : null;
  function reveal(el, delay = 0) {
    el.classList.add("reveal");
    el.style.setProperty("--d", delay);
    if (io) io.observe(el); else el.classList.add("in");
  }

  function countUp(el, to) {
    if (reduced || to < 2) { el.textContent = to.toLocaleString(); return; }
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / 1200, 1);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))).toLocaleString();
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // --------------------------------------------------------- features
  const featList = $("#featList");
  FEATURES.forEach(([title, text], i) => {
    const li = h("li", { class: "feat" }, h("span", { class: "n" }, String(i + 1).padStart(2, "0")), h("div", {}, h("h3", {}, title), h("p", {}, text)));
    featList.append(li);
    reveal(li, i % 4);
  });
  document.querySelectorAll(".split-side, section .reveal").forEach((el) => reveal(el));

  // --------------------------------------------------------- commands
  let commands = [];
  const state = { q: "", cat: "All" };
  const list = $("#cmdList");

  function renderChips() {
    const chips = $("#chips");
    chips.replaceChildren();
    const cats = ["All", ...new Set(commands.map((c) => c.category)), "Staff only"];
    for (const cat of cats) {
      const b = h("button", { class: "chip", type: "button", "aria-pressed": String(state.cat === cat) }, cat);
      b.addEventListener("click", () => { state.cat = cat; renderChips(); renderCommands(); });
      chips.append(b);
    }
  }

  function renderCommands() {
    const q = state.q.toLowerCase();
    const shown = commands.filter((c) => {
      if (state.cat === "Staff only" && !c.staff) return false;
      if (state.cat !== "All" && state.cat !== "Staff only" && c.category !== state.cat) return false;
      return !q || `${c.name} ${c.usage} ${c.description} ${c.category}`.toLowerCase().includes(q);
    });
    $("#count").textContent = `${shown.length} command${shown.length === 1 ? "" : "s"}`;
    list.replaceChildren();
    if (!shown.length) list.append(h("p", { class: "empty" }, "No commands match your search."));
    shown.forEach((c, i) => {
      const prefix = c.prefixOnly ? "!" : "/";
      const row = h("button", { class: "cmd", type: "button", title: "Click to copy" },
        h("span", { class: "cmd-name" }, prefix + c.name, c.prefixOnly ? null : h("small", {}, `  or !${c.name}`)),
        h("span", { class: "cmd-desc" }, h("span", {}, c.description), h("code", {}, prefix + c.usage)),
        h("span", { class: "badges" },
          c.staff ? h("span", { class: "badge staff" }, "Staff") : null,
          c.prefixOnly ? h("span", { class: "badge" }, "Prefix only") : null,
          h("span", { class: "badge" }, c.category)));
      row.style.setProperty("--i", Math.min(i, 14));
      row.addEventListener("click", () => {
        const text = prefix + c.usage;
        (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast(`Copied ${text}`), () => toast(text));
      });
      list.append(row);
    });
  }
  $("#q").addEventListener("input", (e) => { state.q = e.target.value; renderCommands(); });

  // ----------------------------------------------------- announcements
  const TAG = { new: "New", update: "Update", fix: "Fix", maintenance: "Maintenance", news: "News" };
  function renderAnnouncements(items) {
    const box = $("#timeline");
    box.replaceChildren();
    if (!items.length) return box.append(h("p", { class: "empty" }, "No announcements yet. Check back soon."));
    const sorted = [...items].sort((a, b) => (b.pinned - a.pinned) || (b.date - a.date));
    sorted.forEach((a, i) => {
      const body = h("p", { class: "post-body" }, a.body);
      const long = a.body.length > 320 || a.body.split("\n").length > 5;
      const post = h("article", { class: "post" + (a.pinned ? " pinned" : "") },
        h("div", { class: "post-meta" },
          h("span", { class: `pill ${a.tag}` }, TAG[a.tag] || "News"),
          a.pinned ? h("span", {}, "Pinned") : null,
          h("time", { datetime: new Date(a.date).toISOString() }, new Date(a.date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })),
          a.edited ? h("span", {}, "(edited)") : null),
        h("h3", {}, a.title), body);
      if (long) {
        body.classList.add("clamp");
        const more = h("button", { class: "more", type: "button" }, "Read more");
        more.addEventListener("click", () => { const open = body.classList.toggle("clamp"); more.textContent = open ? "Read more" : "Show less"; });
        post.append(more);
      }
      box.append(post);
      reveal(post, Math.min(i, 3));
    });
  }

  // ------------------------------------------------------------ load
  fetch("/api/site")
    .then((r) => r.json())
    .then(({ announcements, commands: cmds, settings }) => {
      commands = cmds;
      renderChips();
      renderCommands();
      renderAnnouncements(announcements);
      document.querySelectorAll(".invite-link").forEach((a) => {
        if (settings.invite) { a.href = settings.invite; a.target = "_blank"; a.rel = "noopener"; }
        else { a.setAttribute("aria-disabled", "true"); a.title = "Invite link not set yet"; }
      });
      if (settings.support) { const s = $(".support-link"); s.href = settings.support; s.hidden = false; }
      $("#stats").hidden = false;
      countUp($('[data-count="commands"]'), cmds.length);
    })
    .catch(() => {
      list.append(h("p", { class: "empty" }, "Couldn't load commands right now. Try refreshing."));
      $("#timeline").append(h("p", { class: "empty" }, "Couldn't load announcements right now."));
    });

  fetch("/api/stats")
    .then((r) => r.json())
    .then(({ stats }) => {
      for (const key of ["servers", "members"]) {
        const dd = $(`[data-count="${key}"]`);
        if (stats) countUp(dd, stats[key]); else dd.parentElement.hidden = true;
      }
    })
    .catch(() => {});

  // ----------------------------------------------------------- embers
  const canvas = $("#embers");
  if (!reduced && canvas.getContext) {
    const ctx = canvas.getContext("2d");
    let w, h2, dots;
    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = innerWidth; h2 = innerHeight;
      canvas.width = w * dpr; canvas.height = h2 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      dots = Array.from({ length: Math.round(Math.min(90, w / 14)) }, () => spawn(true));
    };
    const spawn = (anywhere) => ({
      x: Math.random() * w, y: anywhere ? Math.random() * h2 : h2 + 10,
      r: Math.random() * 1.8 + .4, v: Math.random() * .5 + .15, s: Math.random() * Math.PI * 2, a: Math.random() * .6 + .2,
    });
    const frame = (t) => {
      ctx.clearRect(0, 0, w, h2);
      for (const d of dots) {
        d.y -= d.v;
        const x = d.x + Math.sin(t / 1800 + d.s) * 14;
        if (d.y < -10) Object.assign(d, spawn(false));
        ctx.beginPath();
        ctx.arc(x, d.y, d.r, 0, 6.283);
        ctx.fillStyle = `rgba(88, 211, 255, ${d.a * (0.6 + 0.4 * Math.sin(t / 700 + d.s))})`;
        ctx.shadowColor = "#2f8bff"; ctx.shadowBlur = 8;
        ctx.fill();
      }
      if (!document.hidden) requestAnimationFrame(frame);
    };
    resize();
    addEventListener("resize", resize);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) requestAnimationFrame(frame); });
    requestAnimationFrame(frame);
  }
})();
