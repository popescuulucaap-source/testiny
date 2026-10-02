"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const store = require("./store");
const defaults = require("./defaults");

const PORT = Number(process.env.PORT) || 3000;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "";
const SECRET =
  process.env.SESSION_SECRET ||
  crypto.createHash("sha256").update("testiny-session:" + ADMIN_PASSWORD).digest("hex");
const PUBLIC_DIR = path.join(__dirname, "public");
const TAGS = { new: "🆕 New", update: "🔧 Update", fix: "🐛 Fix", maintenance: "⚠️ Maintenance", news: "📣 News" };
const MIME = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon",
  ".webp": "image/webp", ".json": "application/json", ".txt": "text/plain; charset=utf-8",
};

// ------------------------------------------------------------ helpers
function json(res, status, obj, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers });
  res.end(JSON.stringify(obj));
}
const httpError = (status, message) => Object.assign(new Error(message), { status });

function readJson(req, limit = 300_000) {
  return new Promise((resolve, reject) => {
    if (!(req.headers["content-type"] || "").startsWith("application/json")) {
      return reject(httpError(415, "Content-Type must be application/json"));
    }
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > limit) {
        reject(httpError(413, "Request too large"));
        req.destroy();
      } else chunks.push(c);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString() || "{}"));
      } catch {
        reject(httpError(400, "Invalid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function cookies(req) {
  const out = {};
  for (const part of (req.headers.cookie || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

const sign = (v) => crypto.createHmac("sha256", SECRET).update(v).digest("hex");
function makeToken() {
  const exp = String(Date.now() + 7 * 86400e3);
  return `${exp}.${sign(exp)}`;
}
function validToken(t) {
  if (!t || !ADMIN_PASSWORD) return false;
  const [exp, sig] = t.split(".");
  if (!exp || !sig) return false;
  const good = sign(exp);
  if (sig.length !== good.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(good))) return false;
  return Number(exp) > Date.now();
}
const isAdmin = (req) => validToken(cookies(req).session);

function sameText(a, b) {
  const ha = crypto.createHash("sha256").update(String(a)).digest();
  const hb = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(ha, hb);
}

const attempts = new Map();
const clientIp = (req) => (req.headers["x-forwarded-for"] || req.socket.remoteAddress || "").split(",")[0].trim();
function locked(ip) {
  const a = attempts.get(ip);
  if (a && Date.now() >= a.until) attempts.delete(ip);
  return Boolean(attempts.get(ip) && attempts.get(ip).n >= 5);
}
function failed(ip) {
  const a = attempts.get(ip) || { n: 0, until: 0 };
  a.n += 1;
  a.until = Date.now() + 15 * 60e3;
  attempts.set(ip, a);
}

// ---------------------------------------------------------- validation
const str = (v, max) => String(v ?? "").trim().slice(0, max);
function cleanUrl(v) {
  const s = str(v, 300);
  if (!s) return "";
  try {
    const u = new URL(s);
    return u.protocol === "https:" ? u.toString() : "";
  } catch {
    return "";
  }
}
function cleanAnnouncement(b) {
  const title = str(b.title, 100);
  const body = str(b.body, 4000);
  if (!title || !body) throw httpError(400, "Title and text are required.");
  return { title, body, tag: TAGS[b.tag] ? b.tag : "news", pinned: Boolean(b.pinned) };
}
function cleanCommands(list) {
  if (!Array.isArray(list) || list.length > 200) throw httpError(400, "Invalid command list.");
  return list
    .map((c) => ({
      name: str(c.name, 40).replace(/^[/!]+/, ""),
      category: str(c.category, 30) || "Other",
      usage: str(c.usage, 120),
      description: str(c.description, 300),
      staff: Boolean(c.staff),
      prefixOnly: Boolean(c.prefixOnly),
    }))
    .filter((c) => c.name);
}

// -------------------------------------------------------------- data
const getAnnouncements = () => store.get("announcements", defaults.announcements);
const getCommands = () => store.get("commands", defaults.commands);
async function getSettings() {
  const s = await store.get("settings", {});
  return { invite: s.invite || process.env.INVITE_URL || "", support: s.support || process.env.SUPPORT_URL || "" };
}

let statsCache = { at: 0, data: null };
async function getStats() {
  const token = process.env.DISCORD_TOKEN;
  if (!token) return null;
  if (Date.now() - statsCache.at < 5 * 60e3) return statsCache.data;
  let data = statsCache.data;
  try {
    const r = await fetch("https://discord.com/api/v10/users/@me/guilds?with_counts=true&limit=200", {
      headers: { Authorization: `Bot ${token}` },
    });
    if (r.ok) {
      const g = await r.json();
      data = { servers: g.length, members: g.reduce((s, x) => s + (x.approximate_member_count || 0), 0) };
    }
  } catch {
    /* keep the old numbers */
  }
  statsCache = { at: Date.now(), data };
  return data;
}

async function postToDiscord(a) {
  const url = process.env.DISCORD_WEBHOOK_URL;
  if (!url) return null;
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: "Testiny",
        embeds: [{ title: `${TAGS[a.tag]}: ${a.title}`.slice(0, 256), description: a.body.slice(0, 4000), color: 0x2f8bff, timestamp: new Date(a.date).toISOString() }],
        allowed_mentions: { parse: [] },
      }),
    });
    return r.ok;
  } catch {
    return false;
  }
}

// --------------------------------------------------------------- API
async function api(req, res, url) {
  const m = req.method;
  const p = url.pathname;

  if (m === "GET" && p === "/api/site") {
    return json(res, 200, { announcements: await getAnnouncements(), commands: await getCommands(), settings: await getSettings() });
  }
  if (m === "GET" && p === "/api/stats") return json(res, 200, { stats: await getStats() });
  if (m === "GET" && p === "/api/me") {
    return json(res, 200, { admin: isAdmin(req), configured: Boolean(ADMIN_PASSWORD), webhook: Boolean(process.env.DISCORD_WEBHOOK_URL), persistent: store.persistent });
  }

  if (m === "POST" && p === "/api/login") {
    if (!ADMIN_PASSWORD) throw httpError(503, "Admin is disabled. Set the ADMIN_PASSWORD environment variable.");
    const ip = clientIp(req);
    if (locked(ip)) throw httpError(429, "Too many attempts. Try again in 15 minutes.");
    const body = await readJson(req);
    if (!sameText(body.password || "", ADMIN_PASSWORD)) {
      failed(ip);
      throw httpError(401, "Wrong password.");
    }
    attempts.delete(ip);
    const secure = req.headers["x-forwarded-proto"] === "https" ? "; Secure" : "";
    return json(res, 200, { ok: true }, { "Set-Cookie": `session=${makeToken()}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800${secure}` });
  }
  if (m === "POST" && p === "/api/logout") {
    return json(res, 200, { ok: true }, { "Set-Cookie": "session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0" });
  }

  // everything below needs the admin login
  if (!p.startsWith("/api/") || !["POST", "PUT", "DELETE"].includes(m)) throw httpError(404, "Not found");
  if (!isAdmin(req)) throw httpError(401, "Please log in.");

  if (m === "POST" && p === "/api/announcements") {
    const body = await readJson(req);
    const a = { id: crypto.randomUUID(), ...cleanAnnouncement(body), date: Date.now() };
    const list = await getAnnouncements();
    list.unshift(a);
    await store.set("announcements", list.slice(0, 200));
    const discord = body.discord ? await postToDiscord(a) : null;
    return json(res, 200, { ok: true, announcement: a, discord });
  }
  const one = p.match(/^\/api\/announcements\/([A-Za-z0-9-]+)$/);
  if (one && m === "PUT") {
    const clean = cleanAnnouncement(await readJson(req));
    const list = await getAnnouncements();
    const a = list.find((x) => x.id === one[1]);
    if (!a) throw httpError(404, "Announcement not found.");
    Object.assign(a, clean, { edited: Date.now() });
    await store.set("announcements", list);
    return json(res, 200, { ok: true, announcement: a });
  }
  if (one && m === "DELETE") {
    const list = (await getAnnouncements()).filter((x) => x.id !== one[1]);
    await store.set("announcements", list);
    return json(res, 200, { ok: true });
  }
  if (m === "PUT" && p === "/api/commands") {
    const list = cleanCommands((await readJson(req)).commands);
    await store.set("commands", list);
    return json(res, 200, { ok: true, commands: list });
  }
  if (m === "POST" && p === "/api/commands/reset") {
    await store.set("commands", defaults.commands);
    return json(res, 200, { ok: true, commands: defaults.commands });
  }
  if (m === "PUT" && p === "/api/settings") {
    const b = await readJson(req);
    const s = { invite: cleanUrl(b.invite), support: cleanUrl(b.support) };
    await store.set("settings", s);
    return json(res, 200, { ok: true, settings: await getSettings() });
  }
  throw httpError(404, "Not found");
}

// ------------------------------------------------------------ static
function serveStatic(req, res, url) {
  let rel;
  try {
    rel = decodeURIComponent(url.pathname);
  } catch {
    return json(res, 400, { error: "Bad request" });
  }
  if (rel === "/") rel = "/index.html";
  else if (rel === "/admin") rel = "/admin.html";
  const file = path.normalize(path.join(PUBLIC_DIR, rel));
  if (!file.startsWith(PUBLIC_DIR + path.sep)) return json(res, 403, { error: "Forbidden" });
  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      return res.end("Not found");
    }
    const ext = path.extname(file);
    const cache = ext === ".html" ? "no-cache" : "public, max-age=3600";
    res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream", "Cache-Control": cache });
    res.end(data);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "same-origin");
  res.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
      "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
  );
  try {
    const url = new URL(req.url, "http://localhost");
    if (url.pathname === "/healthz") return json(res, 200, { ok: true });
    if (url.pathname.startsWith("/api/")) return await api(req, res, url);
    if (req.method !== "GET" && req.method !== "HEAD") return json(res, 405, { error: "Method not allowed" });
    return serveStatic(req, res, url);
  } catch (err) {
    if (!err.status) console.error(err);
    if (!res.headersSent) json(res, err.status || 500, { error: err.status ? err.message : "Server error" });
  }
});

store
  .init()
  .then(() => {
    server.listen(PORT, () => {
      console.log(`Website running on port ${PORT} (${store.persistent ? "Postgres" : "file"} storage)`);
      if (!ADMIN_PASSWORD) console.warn("ADMIN_PASSWORD is not set, so /admin is disabled.");
    });
  })
  .catch((err) => {
    console.error("Could not start storage:", err.message);
    process.exit(1);
  });
