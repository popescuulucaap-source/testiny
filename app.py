import os
import json
import secrets
import threading
import time
from datetime import timedelta
from collections import deque
from hmac import compare_digest
from functools import wraps
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET

import requests
import psycopg
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", secrets.token_urlsafe(48))
app.permanent_session_lifetime = timedelta(days=3650)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
APP_STARTED_AT = time.time()
APP_REQUEST_COUNT = 0
APP_METRICS_LOCK = threading.Lock()


@app.before_request
def count_site_request():
    global APP_REQUEST_COUNT
    with APP_METRICS_LOCK:
        APP_REQUEST_COUNT += 1


@app.template_filter("datetimeformat")
def format_timestamp(value):
    try:
        dt = __import__("datetime").datetime
        return dt.fromtimestamp(float(value), __import__("datetime").timezone.utc).strftime("%b %d, %H:%M UTC")
    except (TypeError, ValueError, OSError):
        return "unknown"


@app.template_filter("durationformat")
def format_duration(value):
    seconds = max(0, int(value or 0))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://testiny-7wuu.onrender.com/oauth/callback")
BOT_BRIDGE_SECRET = os.getenv("NIGHTFALL_BRIDGE_SECRET", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
INVITE_URL = os.getenv("INVITE_URL", "#")
SUPPORT_URL = (os.getenv("SUPPORT_URL") or os.getenv("SUPPORT_SERVER_URL") or os.getenv("SUPPORT_SERVER") or "https://discord.gg/ddjhskT4VY").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
NIGHTFALL_YOUTUBE_CHANNEL_ID = os.getenv("NIGHTFALL_YOUTUBE_CHANNEL_ID", "").strip()
ROBLOX_BRIDGE_SECRET = (os.getenv("ROBLOX_BRIDGE_SECRET") or BOT_BRIDGE_SECRET).strip()

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8

# Only settings that the bot actually reads are editable from the dashboard.
CHANNEL_SETTINGS = {
    "logs_channel_id", "ticket_category_id", "ticket_panel_channel_id",
    "welcome_channel_id", "leave_channel_id", "verification_channel_id",
    "command_channel_id", "vouch_channel_id", "feedback_channel_id",
    "proof_channel_id", "gamble_channel_id", "staff_application_channel_id",
    "jail_category_id", "jail_chat_channel_id", "jail_appeal_channel_id",
    "autoreaction_channel_id",
}
ROLE_SETTINGS = {"staff_role_id", "autorole_id", "booster_role_id", "jail_role_id", "verified_role_id", "unverified_role_id"}
TOGGLE_SETTINGS = {"anti_raid", "anti_nuke", "anti_link", "j4j", "j4j_dm", "jail_enabled"}
TEXT_SETTINGS = {"prefix", "autoreaction_emoji", "appeal_invite_url"}
EDITABLE_SETTINGS = CHANNEL_SETTINGS | ROLE_SETTINGS | TOGGLE_SETTINGS | TEXT_SETTINGS | {"appeal_server_id", "ticket_options", "ticket_questions"}
SETTING_GROUPS = [
    ("general", "General", "Identity and moderation logging", [("prefix", "Command prefix", "text"), ("logs_channel_id", "Logs channel ID", "id"), ("staff_role_id", "Staff role ID", "id")]),
    ("community", "Community", "Welcome, feedback, invites, applications and more", [("welcome_channel_id", "Welcome channel ID", "id"), ("leave_channel_id", "Leave channel ID", "id"), ("autorole_id", "Auto role ID", "id"), ("vouch_channel_id", "Vouch channel ID", "id"), ("feedback_channel_id", "Feedback channel ID", "id"), ("proof_channel_id", "Proof channel ID", "id"), ("booster_role_id", "Booster role ID", "id"), ("staff_application_channel_id", "Applications channel ID", "id"), ("autoreaction_channel_id", "Auto reaction channel ID", "id"), ("autoreaction_emoji", "Auto reaction emoji", "text")]),
    ("security", "Security", "Protection, verification and command access", [("anti_raid", "Anti raid protection", "toggle"), ("anti_nuke", "Anti nuke protection", "toggle"), ("anti_link", "Block links", "toggle"), ("j4j", "Join for join", "toggle"), ("j4j_dm", "J4J direct messages", "toggle"), ("verification_channel_id", "Verification channel ID", "id"), ("command_channel_id", "Command only channel ID", "id")]),
    ("tickets", "Tickets & appeals", "Ticket panel, categories and appeal routing", [("ticket_panel_channel_id", "Ticket panel channel ID", "id"), ("ticket_category_id", "Ticket category ID", "id"), ("ticket_options", "Ticket types (comma separated)", "list"), ("ticket_questions", "Ticket questions (JSON)", "json"), ("appeal_server_id", "Appeal server ID", "id"), ("appeal_invite_url", "Appeal invite URL", "text")]),
    ("moderation", "Moderation & jail", "Jail roles, rooms and game channel", [("jail_role_id", "Jail role ID", "id"), ("jail_category_id", "Jail category ID", "id"), ("jail_chat_channel_id", "Jail chat channel ID", "id"), ("jail_appeal_channel_id", "Jail appeals channel ID", "id"), ("gamble_channel_id", "Games channel ID", "id")]),
]


def discord_headers():
    return {"Authorization": f"Bearer {session['access_token']}"}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "access_token" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def refresh_discord_session():
    if "access_token" not in session or "refresh_token" not in session:
        return False
    expires_at = float(session.get("token_expires_at", 0) or 0)
    if expires_at and time.time() < expires_at - 60:
        return True
    try:
        response = requests.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": session["refresh_token"],
            },
            timeout=12,
        )
        if response.status_code != 200:
            return False
        data = response.json()
        session["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            session["refresh_token"] = data["refresh_token"]
        session["token_expires_at"] = time.time() + int(data.get("expires_in", 604800))
        session.permanent = True
        return True
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False

@app.before_request
def require_discord_for_site():
    # Public browsing is allowed. State-changing/private areas still require Discord.
    public_get = {"/", "/commands", "/planets", "/guidelines", "/announcements", "/suggestions", "/support"}
    public_secret_api = {"/api/arcade/start", "/api/arcade/hit", "/api/arcade/finish"}
    public_bot_api = {"/api/bot/heartbeat", "/api/bot/pull"}
    endpoint = request.endpoint or ""
    if endpoint in {"login", "oauth_callback", "health"} or endpoint.startswith("static"):
        return None
    if request.method in {"GET", "HEAD"} and request.path in public_get:
        return None
    if request.path in public_secret_api or request.path in public_bot_api:
        return None
    if "access_token" not in session:
        return redirect(url_for("login", next=request.path))
    if not refresh_discord_session():
        session.clear()
        return redirect(url_for("login", next=request.path))
    return None

BOT_LOCK = threading.Lock()
BOT_GUILDS = {}
BOT_LAST_SEEN = 0.0
BOT_JOBS = deque()
BOT_NEXT_JOB_ID = 1


def bot_online():
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row = conn.execute("SELECT last_seen FROM bot_bridge_state WHERE state_id = 1").fetchone()
            return bool(row and row[0] and time.time() - row[0] < 75)
        except psycopg.Error as exc:
            app.logger.warning("Could not read shared bot heartbeat: %s", type(exc).__name__)
    with BOT_LOCK:
        return bool(BOT_LAST_SEEN and time.time() - BOT_LAST_SEEN < 75)


def queue_bot_job(guild_id, kind, payload):
    global BOT_NEXT_JOB_ID
    if DATABASE_URL:
        with db_connect() as conn:
            row = conn.execute(
                "INSERT INTO bot_jobs (guild_id, kind, payload) VALUES (%s, %s, %s) RETURNING job_id",
                (str(guild_id), kind, json.dumps(payload)),
            ).fetchone()
            return row[0]
    with BOT_LOCK:
        job_id = BOT_NEXT_JOB_ID
        BOT_NEXT_JOB_ID += 1
        BOT_JOBS.append({"id": job_id, "guild_id": str(guild_id), "kind": kind, "payload": payload})
    return job_id


def bot_guild_snapshot():
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row = conn.execute("SELECT guilds FROM bot_bridge_state WHERE state_id = 1").fetchone()
            return json.loads(row[0]) if row and row[0] else []
        except (psycopg.Error, ValueError, TypeError) as exc:
            app.logger.warning("Could not read shared bot state: %s", type(exc).__name__)
    with BOT_LOCK:
        return list(BOT_GUILDS.values())


def require_bot_key():
    supplied = request.headers.get("X-Nightfall-Bridge-Key", "")
    if not BOT_BRIDGE_SECRET or not compare_digest(supplied, BOT_BRIDGE_SECRET):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None


def record_bot_event(event_type, guild_id=None, guild_name="", user_id=None, username="", command_name="", metadata=None):
    if not DATABASE_URL:
        return
    try:
        with db_connect() as conn:
            conn.execute(
                "INSERT INTO bot_telemetry (event_type,guild_id,guild_name,user_id,username,command_name,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (str(event_type)[:40], str(guild_id) if guild_id is not None else None, str(guild_name)[:120],
                 str(user_id) if user_id is not None else None, str(username)[:120], str(command_name)[:120],
                 json.dumps(metadata or {})[:4000]),
            )
            conn.commit()
    except psycopg.Error as exc:
        app.logger.warning("Could not record bot telemetry: %s", type(exc).__name__)

@app.post("/api/bot/events")
def bot_events():
    denied = require_bot_key()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    events = payload.get("events")
    if not isinstance(events, list) or len(events) > 200:
        return jsonify({"ok": False, "error": "events must be a list of up to 200 items"}), 400
    if not DATABASE_URL:
        return jsonify({"ok": True, "stored": 0})
    with db_connect() as conn:
        for item in events:
            if not isinstance(item, dict) or not item.get("event_type"):
                continue
            conn.execute(
                "INSERT INTO bot_telemetry (event_type,guild_id,guild_name,user_id,username,command_name,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (str(item.get("event_type"))[:40], str(item.get("guild_id")) if item.get("guild_id") is not None else None,
                 str(item.get("guild_name") or "")[:120], str(item.get("user_id")) if item.get("user_id") is not None else None,
                 str(item.get("username") or "")[:120], str(item.get("command_name") or "")[:120],
                 json.dumps(item.get("metadata") if isinstance(item.get("metadata"), dict) else {})[:4000]),
            )
        conn.commit()
    return jsonify({"ok": True})

@app.get("/admin/audit")
def admin_audit():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    events = []
    summary = {"commands": 0, "messages": 0, "tickets": 0, "forms": 0}
    if DATABASE_URL:
        with db_connect() as conn:
            rows = conn.execute("SELECT event_type,guild_id,guild_name,user_id,username,command_name,metadata,created_at FROM bot_telemetry ORDER BY id DESC LIMIT 500").fetchall()
            events = [{"event_type":r[0],"guild_id":r[1],"guild_name":r[2],"user_id":r[3],"username":r[4],"command_name":r[5],"metadata":r[6],"created_at":r[7]} for r in rows]
            for key, label in (("command_used","commands"),("message_seen","messages"),("ticket_created","tickets"),("form_submitted","forms")):
                row = conn.execute("SELECT COUNT(*) FROM bot_telemetry WHERE event_type=%s", (key,)).fetchone()
                summary[label] = int(row[0] or 0)
    return render_template("admin_audit.html", events=events, summary=summary)

@app.post("/api/bot/heartbeat")
def bot_heartbeat():
    global BOT_LAST_SEEN, BOT_GUILDS
    denied = require_bot_key()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    guilds = payload.get("guilds")
    if not isinstance(guilds, list):
        return jsonify({"ok": False, "error": "guilds must be a list"}), 400
    normalized = {}
    for guild in guilds:
        if isinstance(guild, dict) and guild.get("id"):
            normalized[str(guild["id"])] = {
                "id": str(guild["id"]),
                "name": str(guild.get("name") or "Discord server"),
                "member_count": guild.get("member_count"),
                "invite_url": str(guild.get("invite_url") or "").strip(),
                "settings": guild.get("settings") if isinstance(guild.get("settings"), dict) else {},
            }
    last_seen = time.time()
    guild_snapshot = list(normalized.values())
    if DATABASE_URL:
        with db_connect() as conn:
            conn.execute(
                "INSERT INTO bot_bridge_state (state_id, last_seen, guilds) VALUES (1, %s, %s) "
                "ON CONFLICT (state_id) DO UPDATE SET last_seen = EXCLUDED.last_seen, guilds = EXCLUDED.guilds",
                (last_seen, json.dumps(guild_snapshot)),
            )
    with BOT_LOCK:
        BOT_GUILDS = normalized
        BOT_LAST_SEEN = last_seen
    return jsonify({"ok": True})


@app.get("/api/bot/pull")
def bot_pull_jobs():
    denied = require_bot_key()
    if denied:
        return denied
    if DATABASE_URL:
        with db_connect() as conn:
            rows = conn.execute(
                "SELECT job_id, guild_id, kind, payload FROM bot_jobs "
                "ORDER BY job_id LIMIT 100 FOR UPDATE SKIP LOCKED"
            ).fetchall()
            if rows:
                conn.execute("DELETE FROM bot_jobs WHERE job_id = ANY(%s)", ([row[0] for row in rows],))
            jobs = [{"id": row[0], "guild_id": row[1], "kind": row[2], "payload": json.loads(row[3])} for row in rows]
        return jsonify({"ok": True, "jobs": jobs})
    with BOT_LOCK:
        jobs = list(BOT_JOBS)
        BOT_JOBS.clear()
    return jsonify({"ok": True, "jobs": jobs})


def user_can_manage_guild(guild_id):
    try:
        response = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
        if response.status_code != 200:
            return False
        guild = next((item for item in response.json() if str(item.get("id")) == str(guild_id)), None)
        if not guild:
            return False
        permissions = int(guild.get("permissions", "0"))
        return bool((permissions & MANAGE_GUILD) == MANAGE_GUILD or (permissions & ADMINISTRATOR) == ADMINISTRATOR)
    except (requests.RequestException, ValueError, TypeError):
        return False


@app.context_processor
def site_context():
    return {"invite_url": INVITE_URL, "support_url": SUPPORT_URL}

def db_connect():
    return psycopg.connect(DATABASE_URL) if DATABASE_URL else None

def current_discord_user_id():
    user = session.get("user") or {}
    value = user.get("id")
    return str(value) if value else ""

def get_roblox_link(discord_id):
    if not DATABASE_URL or not discord_id:
        return None
    with db_connect() as conn:
        row = conn.execute(
            "SELECT discord_id, roblox_user_id, link_token, premium, premium_source, premium_expires_at, updated_at FROM roblox_links WHERE discord_id=%s",
            (str(discord_id),),
        ).fetchone()
    if not row:
        return None
    return {
        "discord_id": row[0], "roblox_user_id": row[1], "link_token": row[2],
        "premium": bool(row[3]), "premium_source": row[4],
        "premium_expires_at": float(row[5] or 0), "updated_at": row[6],
    }

def roblox_premium_active(link):
    if not link:
        return False
    if link["premium"]:
        return True
    return float(link.get("premium_expires_at") or 0) > time.time()



REPO_SYNC_LOCK = threading.Lock()
REPO_SYNC_LAST_CHECK = 0.0
REPO_SYNC_INTERVAL = 300

def sync_repository_updates(force=False):
    """Turn new GitHub commits into public site/bot updates."""
    global REPO_SYNC_LAST_CHECK
    if not DATABASE_URL:
        return
    now = time.time()
    with REPO_SYNC_LOCK:
        if not force and now - REPO_SYNC_LAST_CHECK < REPO_SYNC_INTERVAL:
            return
        REPO_SYNC_LAST_CHECK = now
    repos = [
        ("site", "Website Update", "popescuulucaap-source/testiny"),
        ("bot", "Bot Update", "popescuulucaap-source/night-fall-discord-bot"),
    ]
    try:
        with db_connect() as conn:
            for repo_kind, label, repo_name in repos:
                response = requests.get(
                    f"https://api.github.com/repos/{repo_name}/commits",
                    params={"per_page": 1},
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "Nightfall-Updates"},
                    timeout=8,
                )
                if response.status_code != 200:
                    continue
                commits = response.json()
                if not commits:
                    continue
                commit = commits[0]
                sha = str(commit.get("sha") or "")
                message = str(commit.get("commit", {}).get("message") or "Repository update").splitlines()[0].strip()
                if not sha:
                    continue
                row = conn.execute("SELECT commit_sha FROM repository_updates WHERE repo_kind=%s", (repo_kind,)).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO repository_updates (repo_kind, commit_sha, checked_at) VALUES (%s,%s,NOW())",
                        (repo_kind, sha),
                    )
                    continue
                if row[0] == sha:
                    conn.execute("UPDATE repository_updates SET checked_at=NOW() WHERE repo_kind=%s", (repo_kind,))
                    continue
                conn.execute(
                    "INSERT INTO announcements (title, body, date, kind) VALUES (%s,%s,%s,%s)",
                    (
                        f"{label} • {message[:120]}",
                        f"Automatically detected from GitHub commit {sha[:7]}. {message}",
                        __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d"),
                        "bot" if repo_kind == "bot" else "website",
                    ),
                )
                conn.execute(
                    "UPDATE repository_updates SET commit_sha=%s, checked_at=NOW() WHERE repo_kind=%s",
                    (sha, repo_kind),
                )
            conn.commit()
    except (requests.RequestException, ValueError, psycopg.Error) as exc:
        app.logger.warning("Could not sync repository updates: %s", type(exc).__name__)

def init_db():
    if not DATABASE_URL:
        return
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS announcements (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, date TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'website')")
            cur.execute("CREATE TABLE IF NOT EXISTS repository_updates (repo_kind TEXT PRIMARY KEY, commit_sha TEXT NOT NULL, checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("ALTER TABLE announcements ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'website'")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_telemetry (id BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, guild_id TEXT, guild_name TEXT, user_id TEXT, username TEXT, command_name TEXT, metadata TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE INDEX IF NOT EXISTS bot_telemetry_created_at_idx ON bot_telemetry(created_at DESC)")
            cur.execute("SELECT 1 FROM announcements WHERE title=%s LIMIT 1", ("Nightfall Updates Center • Automatic tracking",))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO announcements (title, body, date, kind) VALUES (%s,%s,%s,%s)",
                    (
                        "Nightfall Updates Center • Automatic tracking",
                        "Website and bot changes are now tracked from their GitHub repositories. New commits can appear here automatically, and admins can publish their own site or bot updates from the Admin panel.",
                        "2026-10-05",
                        "website",
                    ),
                )
            # Seed the public bot release announcements once, without duplicating them.
            bot_releases = [
                (
                    "Nightfall v1.0 • Bot Update",
                    "Nightfall v1.0 introduced the core Discord bot experience, moderation tools and server-management features.",
                    "2026-10-01",
                ),
                (
                    "Nightfall v1.1 • Bot Update",
                    "Nightfall v1.1 expanded the bot with additional server tools, protection features and quality-of-life improvements.",
                    "2026-10-03",
                ),
                (
                    "Nightfall v1.2 • Bot Update",
                    "Nightfall v1.2 brought new bot improvements, expanded command support and stronger server-management features.",
                    "2026-10-05",
                ),
            ]
            for title, body, date in bot_releases:
                cur.execute("SELECT 1 FROM announcements WHERE title=%s LIMIT 1", (title,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO announcements (title, body, date, kind) VALUES (%s,%s,%s,%s)",
                        (title, body, date, "bot"),
                    )
            cur.execute("CREATE TABLE IF NOT EXISTS suggestions (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, suggestion TEXT NOT NULL, date TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS custom_commands (id BIGSERIAL PRIMARY KEY, command TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_bridge_state (state_id SMALLINT PRIMARY KEY CHECK (state_id = 1), last_seen DOUBLE PRECISION NOT NULL, guilds TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_jobs (job_id BIGSERIAL PRIMARY KEY, guild_id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS reviews (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, rating INTEGER NOT NULL, review TEXT NOT NULL, date TEXT NOT NULL, approved BOOLEAN NOT NULL DEFAULT TRUE)")
            cur.execute("CREATE TABLE IF NOT EXISTS support_tickets (id BIGSERIAL PRIMARY KEY, token TEXT UNIQUE NOT NULL, name TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS support_messages (id BIGSERIAL PRIMARY KEY, ticket_id BIGINT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE, sender TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS social_videos (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, username TEXT NOT NULL, avatar_url TEXT NOT NULL, video_url TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', strikes INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS social_follows (follower_id TEXT NOT NULL, following_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (follower_id, following_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS social_reports (id BIGSERIAL PRIMARY KEY, video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, reporter_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS site_profiles (discord_id TEXT PRIMARY KEY, username TEXT NOT NULL, avatar_url TEXT NOT NULL DEFAULT '', xp INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS site_xp_events (discord_id TEXT NOT NULL, action TEXT NOT NULL, last_awarded TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (discord_id, action))")
            cur.execute("CREATE TABLE IF NOT EXISTS site_notifications (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, read BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_scores (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, username TEXT NOT NULL, game TEXT NOT NULL, score INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_challenges (discord_id TEXT PRIMARY KEY, started_at DOUBLE PRECISION NOT NULL, hits INTEGER NOT NULL DEFAULT 0, completed BOOLEAN NOT NULL DEFAULT FALSE)")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_rewards (discord_id TEXT PRIMARY KEY, code TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), redeemed_at TIMESTAMPTZ NULL, redeemed_by TEXT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS roblox_links (discord_id TEXT PRIMARY KEY, roblox_user_id TEXT UNIQUE, link_token TEXT UNIQUE NOT NULL, token_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), premium BOOLEAN NOT NULL DEFAULT FALSE, premium_source TEXT NOT NULL DEFAULT 'none', premium_expires_at DOUBLE PRECISION NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            # Safe, backwards-compatible migration. Older installs used code_hash.
            # Keep that legacy column nullable instead of dropping it during startup;
            # this avoids breaking existing rows/constraints while allowing new rows
            # to use the account-bound code column.
            columns = {row[0] for row in cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'arcade_rewards'"
            ).fetchall()}
            if "code" not in columns:
                cur.execute("ALTER TABLE arcade_rewards ADD COLUMN code TEXT")
            if "code_hash" in columns:
                cur.execute("ALTER TABLE arcade_rewards ALTER COLUMN code_hash DROP NOT NULL")
            cur.execute("UPDATE arcade_rewards SET code=%s WHERE code IS NULL OR code=''", ("ducky-squad",))
            cur.execute("ALTER TABLE arcade_rewards ALTER COLUMN code SET NOT NULL")
            cur.execute("CREATE TABLE IF NOT EXISTS site_settings (discord_id TEXT PRIMARY KEY, bio TEXT NOT NULL DEFAULT '', theme TEXT NOT NULL DEFAULT 'default', title TEXT NOT NULL DEFAULT '')")
            cur.execute("CREATE TABLE IF NOT EXISTS site_achievements (discord_id TEXT NOT NULL, achievement TEXT NOT NULL, unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (discord_id, achievement))")
            cur.execute("CREATE TABLE IF NOT EXISTS site_reputation (discord_id TEXT PRIMARY KEY, score INTEGER NOT NULL DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS social_likes (video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (video_id, discord_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS social_comments (id BIGSERIAL PRIMARY KEY, video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, username TEXT NOT NULL, avatar_url TEXT NOT NULL DEFAULT '', body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'approved', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        conn.commit()

def load_announcements():
    sync_repository_updates()
    if not DATABASE_URL:
        return session.get("announcements", [])
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body, date, kind FROM announcements ORDER BY id DESC")
            return [{"id":r[0],"title":r[1],"body":r[2],"date":r[3],"kind":r[4] or "website"} for r in cur.fetchall()]

def save_announcement(title, body, kind="website"):
    date=__import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    if not DATABASE_URL:
        items=session.get("announcements", [])
        items.insert(0,{"title":title,"body":body,"date":date})
        session["announcements"]=items
        return
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO announcements (title, body, date, kind) VALUES (%s, %s, %s, %s)",(title,body,date,kind))
        conn.commit()

def delete_announcement(announcement_id):
    if not DATABASE_URL: return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("DELETE FROM announcements WHERE id = %s",(announcement_id,))
        conn.commit()

def load_custom_commands():
    if not DATABASE_URL: return []
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, command, category, description FROM custom_commands ORDER BY id DESC")
            return [{"id":r[0],"command":r[1],"category":r[2],"description":r[3]} for r in cur.fetchall()]

def save_custom_command(command, category, description):
    if not DATABASE_URL: return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("INSERT INTO custom_commands (command, category, description) VALUES (%s, %s, %s)",(command,category,description))
        conn.commit()

def delete_custom_command(command_id):
    if not DATABASE_URL: return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("DELETE FROM custom_commands WHERE id = %s",(command_id,))
        conn.commit()

def all_commands():
    # Keep the public library limited to commands implemented in main.py.
    # Admin dashboard notes are not executable bot commands.
    return list(COMMANDS)

init_db()
sync_repository_updates(force=True)

@app.get("/")
def index():
    features = [
        ("🛡️","Moderation","Ban, kick, warn, timeout, lock, slowmode and jail."),
        ("🔐","Security","Anti-raid, anti-nuke, anti-link and verification."),
        ("🎫","Tickets","Interactive panels, questions, claims, proof and appeals."),
        ("👋","Server Tools","Welcome, leave, invites, vouches, feedback and boosters."),
        ("⚙️","Dashboard","Manage Nightfall settings, security, tickets and server tools from the web."),
        ("🎁","Giveaways","Prize embeds, timers, winners, rerolls and early endings."),
        ("🎨","AI studio","Ask questions, create stories, jokes, poems, riddles, captions, names and quizzes with Nightfall AI."),
    ]
    return render_template("index.html", features=features, command_count=len(COMMANDS))

@app.route("/admin", methods=["GET","POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        if ADMIN_PASSWORD and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="Incorrect admin password.")
    return render_template("admin_login.html")

@app.get("/admin/panel")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    session.permanent = True
    announcements = load_announcements()
    custom_commands = load_custom_commands()
    guilds = bot_guild_snapshot()
    member_total = sum(int(guild.get("member_count") or 0) for guild in guilds)
    last_seen = BOT_LAST_SEEN
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row = conn.execute("SELECT last_seen FROM bot_bridge_state WHERE state_id = 1").fetchone()
            last_seen = float(row[0]) if row and row[0] else 0.0
        except psycopg.Error as exc:
            app.logger.warning("Could not read admin bot heartbeat: %s", type(exc).__name__)
    with APP_METRICS_LOCK:
        request_count = APP_REQUEST_COUNT
    heartbeat_age = int(max(0, time.time() - last_seen)) if last_seen else None
    snapshot_age = heartbeat_age if guilds else None
    suggestion_count = 0
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()
            suggestion_count = int(row[0] or 0)
        except psycopg.Error as exc:
            app.logger.warning("Could not read suggestion count: %s", type(exc).__name__)
    else:
        suggestion_count = len(session.get("suggestions", []))
    settings_rows = [guild.get("settings") or {} for guild in guilds]
    configured_servers = sum(1 for s in settings_rows if any(v not in (None, "", False, [], {}) for v in s.values()))
    anti_raid_servers = sum(1 for s in settings_rows if s.get("anti_raid"))
    anti_nuke_servers = sum(1 for s in settings_rows if s.get("anti_nuke"))
    jail_servers = sum(1 for s in settings_rows if s.get("jail_enabled"))
    verification_servers = sum(1 for s in settings_rows if s.get("verification_enabled") or s.get("verification_channel_id"))
    ticket_servers = sum(1 for s in settings_rows if s.get("ticket_panel_channel_id") or s.get("ticket_options"))
    avg_members = int(round(member_total / len(guilds))) if guilds else 0
    stats = {
        "bot_online": bot_online(),
        "guild_count": len(guilds),
        "active_guild_count": len(guilds),
        "heartbeat_age": f"{heartbeat_age}s" if heartbeat_age is not None else "—",
        "snapshot_age": f"{snapshot_age}s" if snapshot_age is not None else "—",
        "avg_members": avg_members,
        "suggestion_count": suggestion_count,
        "member_count": member_total,
        "last_seen": last_seen,
        "uptime_seconds": max(0, int(time.time() - APP_STARTED_AT)),
        "request_count": request_count,
        "announcement_count": len(announcements),
        "command_count": len(COMMANDS) + len(custom_commands),
        "custom_command_count": len(custom_commands),
        "database_enabled": bool(DATABASE_URL),
        "configured_servers": configured_servers,
        "anti_raid_servers": anti_raid_servers,
        "anti_nuke_servers": anti_nuke_servers,
        "jail_servers": jail_servers,
        "verification_servers": verification_servers,
        "ticket_servers": ticket_servers,
    }
    stats["telemetry_command_count"] = 0
    stats["telemetry_message_count"] = 0
    stats["telemetry_ticket_count"] = 0
    stats["telemetry_form_count"] = 0
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                for key, field in (("command_used","telemetry_command_count"),("message_seen","telemetry_message_count"),("ticket_created","telemetry_ticket_count"),("form_submitted","telemetry_form_count")):
                    row = conn.execute("SELECT COUNT(*) FROM bot_telemetry WHERE event_type=%s", (key,)).fetchone()
                    stats[field] = int(row[0] or 0)
        except psycopg.Error as exc:
            app.logger.warning("Could not read telemetry counts: %s", type(exc).__name__)
    return render_template("admin.html", announcements=announcements, custom_commands=custom_commands, database_enabled=bool(DATABASE_URL), stats=stats, bot_guilds=guilds)

@app.post("/admin/command")
def admin_command():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    cmd=(request.form.get("command") or "").strip()
    cat=(request.form.get("category") or "Other").strip()
    desc=(request.form.get("description") or "").strip()
    if cmd and desc:
        save_custom_command(cmd,cat,desc)
        save_announcement("Website Update • Command library changed", f"Admin added {cmd} to the {cat} command category.", "website")
    return redirect(url_for("admin"))

@app.post("/admin/announcement")
def admin_announcement():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    title=(request.form.get("title") or "Update").strip()
    body=(request.form.get("body") or "").strip()
    kind=(request.form.get("kind") or "website").strip().lower()
    if kind not in {"bot","website"}: kind="website"
    if title and body: save_announcement(title,body,kind)
    return redirect(url_for("admin"))

@app.post("/admin/announcement/<int:announcement_id>/delete")
def admin_delete_announcement(announcement_id):
    if not session.get("admin"): return redirect(url_for("admin_login"))
    delete_announcement(announcement_id)
    return redirect(url_for("admin"))

@app.post("/admin/command/<int:command_id>/delete")
def admin_delete_command(command_id):
    if not session.get("admin"): return redirect(url_for("admin_login"))
    delete_custom_command(command_id)
    return redirect(url_for("admin"))

@app.get("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))





@app.route("/support")
def support():
    return render_template("support.html")

@app.route("/secrets")
def secrets_page():
    return redirect(url_for("index"))

def _support_ticket_row(row):
    return {
        "id": row[0],
        "token": row[1],
        "name": row[2],
        "subject": row[3],
        "status": row[4],
        "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        "updated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
    }

@app.post("/api/support/tickets")
def create_support_ticket():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "Anonymous").strip()[:40] or "Anonymous"
    subject = str(payload.get("subject") or "Nightfall support").strip()[:120] or "Nightfall support"
    message = str(payload.get("message") or "").strip()[:2000]
    if not message:
        return jsonify({"ok": False, "error": "Write a message first."}), 400
    token = secrets.token_urlsafe(24)
    if not DATABASE_URL:
        tickets = session.get("support_tickets", [])
        ticket = {"id": len(tickets) + 1, "token": token, "name": name, "subject": subject, "status": "open", "messages": [{"from": "user", "text": message, "time": time.time()}]}
        tickets.insert(0, ticket)
        session["support_tickets"] = tickets[:30]
        return jsonify({"ok": True, "ticket": {"id": ticket["id"], "token": token, "status": "open"}})
    now = __import__("datetime").datetime.utcnow()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO support_tickets (token, name, subject, status, created_at, updated_at) VALUES (%s,%s,%s,'open',%s,%s) RETURNING id", (token,name,subject,now,now))
            ticket_id = cur.fetchone()[0]
            cur.execute("INSERT INTO support_messages (ticket_id, sender, message, created_at) VALUES (%s,'user',%s,%s)", (ticket_id,message,now))
        conn.commit()
    return jsonify({"ok": True, "ticket": {"id": ticket_id, "token": token, "status": "open"}})

@app.get("/api/support/tickets/<token>")
def get_support_ticket(token):
    if not DATABASE_URL:
        ticket = next((x for x in session.get("support_tickets", []) if x.get("token") == token), None)
        if not ticket: return jsonify({"ok": False, "error": "Support ticket not found."}), 404
        return jsonify({"ok": True, "ticket": ticket})
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, token, name, subject, status, created_at, updated_at FROM support_tickets WHERE token=%s", (token,))
            row=cur.fetchone()
            if not row: return jsonify({"ok": False, "error": "Support ticket not found."}), 404
            ticket=_support_ticket_row(row)
            cur.execute("SELECT sender, message, created_at FROM support_messages WHERE ticket_id=%s ORDER BY id ASC", (row[0],))
            ticket["messages"]=[{"from":r[0],"text":r[1],"time":r[2].isoformat() if hasattr(r[2],"isoformat") else str(r[2])} for r in cur.fetchall()]
    return jsonify({"ok": True, "ticket": ticket})

@app.post("/api/support/tickets/<token>/messages")
def add_support_message(token):
    payload=request.get_json(silent=True) or {}
    message=str(payload.get("message") or "").strip()[:2000]
    if not message: return jsonify({"ok":False,"error":"Write a message first."}),400
    if not DATABASE_URL:
        tickets=session.get("support_tickets",[])
        ticket=next((x for x in tickets if x.get("token")==token),None)
        if not ticket: return jsonify({"ok":False,"error":"Support ticket not found."}),404
        ticket.setdefault("messages",[]).append({"from":"user","text":message,"time":time.time()})
        session["support_tickets"]=tickets
        return jsonify({"ok":True})
    now=__import__("datetime").datetime.utcnow()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,status FROM support_tickets WHERE token=%s",(token,))
            row=cur.fetchone()
            if not row: return jsonify({"ok":False,"error":"Support ticket not found."}),404
            if row[1] == "closed": return jsonify({"ok":False,"error":"This ticket is closed."}),400
            cur.execute("INSERT INTO support_messages (ticket_id,sender,message,created_at) VALUES (%s,'user',%s,%s)",(row[0],message,now))
            cur.execute("UPDATE support_tickets SET updated_at=%s,status='open' WHERE id=%s",(now,row[0]))
        conn.commit()
    return jsonify({"ok":True})

@app.get("/admin/support")
def admin_support():
    if not session.get("admin"): return redirect(url_for("admin_login"))
    if DATABASE_URL:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, token, name, subject, status, created_at, updated_at FROM support_tickets ORDER BY updated_at DESC LIMIT 100")
                tickets=[_support_ticket_row(r) for r in cur.fetchall()]
                for t in tickets:
                    cur.execute("SELECT sender, message, created_at FROM support_messages WHERE ticket_id=%s ORDER BY id ASC",(t["id"],))
                    t["messages"]=[{"from":r[0],"text":r[1],"time":r[2].isoformat() if hasattr(r[2],"isoformat") else str(r[2])} for r in cur.fetchall()]
    else:
        tickets=session.get("support_tickets",[])
    return render_template("admin_support.html", tickets=tickets)

@app.post("/admin/support/<int:ticket_id>/reply")
def admin_support_reply(ticket_id):
    if not session.get("admin"): return redirect(url_for("admin_login"))
    message=(request.form.get("message") or "").strip()[:2000]
    if message:
        if DATABASE_URL:
            now=__import__("datetime").datetime.utcnow()
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO support_messages (ticket_id,sender,message,created_at) VALUES (%s,'admin',%s,%s)",(ticket_id,message,now))
                    cur.execute("UPDATE support_tickets SET updated_at=%s WHERE id=%s",(now,ticket_id))
                conn.commit()
        else:
            for t in session.get("support_tickets",[]):
                if int(t.get("id",0)) == ticket_id:
                    t.setdefault("messages",[]).append({"from":"admin","text":message,"time":time.time()})
                    break
            session.modified=True
    return redirect(url_for("admin_support"))

def _social_user():
    user = session.get("user")
    if not user:
        return None
    uid = str(user.get("id") or "")
    username = str(user.get("global_name") or user.get("username") or "Discord user")
    avatar = user.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png?size=128"
        if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    )
    return {"id": uid, "username": username, "avatar_url": avatar_url}


def _youtube_url(raw):
    parsed = urlparse((raw or "").strip())
    host = parsed.netloc.lower().split(":")[0]
    if parsed.scheme != "https" or host not in {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}:
        return None
    return parsed.geturl()


def _official_youtube_videos(limit=15):
    """Read the public Nightfall YouTube upload feed."""
    channel_id = NIGHTFALL_YOUTUBE_CHANNEL_ID
    if not channel_id:
        match = re.search(r"youtube\.com/channel/(UC[\w-]+)", "https://www.youtube.com/@nightfall-bot")
        channel_id = match.group(1) if match else ""
    if not channel_id:
        return []
    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
    try:
        response = requests.get(feed_url, timeout=10, headers={"User-Agent": "Nightfall Community"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        ns = {"yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
        videos = []
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry")[:limit]:
            video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title", default="Nightfall upload") or "Nightfall upload").strip()
            published = (entry.findtext("{http://www.w3.org/2005/Atom}published", default="") or "").strip()
            media_group = entry.find("media:group", ns)
            description = ""
            if media_group is not None:
                description = (media_group.findtext("media:description", default="", namespaces=ns) or "").strip()
            if not video_id:
                continue
            videos.append({
                "id": "youtube:" + video_id,
                "discord_id": "",
                "username": "Nightfall • YouTube",
                "avatar_url": "/static/nightfall-logo.svg",
                "video_url": "https://www.youtube.com/watch?v=" + video_id,
                "title": title,
                "description": description[:500],
                "created_at": published,
                "following": False,
                "source": "youtube",
                "official": True,
            })
        return videos
    except (requests.RequestException, ET.ParseError, ValueError) as exc:
        app.logger.warning("Could not load Nightfall YouTube feed: %s", type(exc).__name__)
        return []


@app.get("/community")
def community():
    return redirect(url_for("index"))


@app.get("/api/social/feed")
def social_feed():
    official_videos = _official_youtube_videos()
    viewer = _social_user()
    viewer_id = viewer["id"] if viewer else ""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT v.id,v.discord_id,v.username,v.avatar_url,v.video_url,v.title,v.description,v.created_at, "
                "EXISTS(SELECT 1 FROM social_follows f WHERE f.follower_id=%s AND f.following_id=v.discord_id) "
                "FROM social_videos v WHERE v.status='approved' ORDER BY v.id DESC LIMIT 100",
                (viewer_id,),
            )
            videos = [{
                "id": r[0], "discord_id": r[1], "username": r[2], "avatar_url": r[3],
                "video_url": r[4], "title": r[5], "description": r[6],
                "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                "following": bool(r[8]),
            } for r in cur.fetchall()]
    return jsonify({"ok": True, "videos": official_videos + videos})


@app.post("/api/social/videos")
@login_required
def social_submit_video():
    user = _social_user()
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()[:120]
    description = str(payload.get("description") or "").strip()[:500]
    video_url = _youtube_url(payload.get("video_url"))
    if not title or not video_url:
        return jsonify({"ok": False, "error": "Add a title and a valid HTTPS YouTube link."}), 400
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Community storage is not configured yet."}), 503
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO social_videos (discord_id,username,avatar_url,video_url,title,description,status) "
                "VALUES (%s,%s,%s,%s,%s,%s,'pending')",
                (user["id"], user["username"], user["avatar_url"], video_url, title, description),
            )
        conn.commit()
    return jsonify({"ok": True, "message": "Submitted for moderator approval."})


@app.post("/api/social/follow/<discord_id>")
@login_required
def social_follow(discord_id):
    viewer = _social_user()
    target = str(discord_id).strip()
    if not target or target == viewer["id"]:
        return jsonify({"ok": False, "error": "You cannot follow yourself."}), 400
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Community storage is not configured yet."}), 503
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM social_follows WHERE follower_id=%s AND following_id=%s", (viewer["id"], target))
            exists = cur.fetchone()
            if exists:
                cur.execute("DELETE FROM social_follows WHERE follower_id=%s AND following_id=%s", (viewer["id"], target))
                following = False
            else:
                cur.execute("INSERT INTO social_follows (follower_id,following_id) VALUES (%s,%s)", (viewer["id"], target))
                following = True
        conn.commit()
    return jsonify({"ok": True, "following": following})


@app.post("/api/social/report/<int:video_id>")
@login_required
def social_report(video_id):
    viewer = _social_user()
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "").strip()[:300]
    if not reason:
        return jsonify({"ok": False, "error": "Give a short reason for the report."}), 400
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Community storage is not configured yet."}), 503
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM social_videos WHERE id=%s AND status='approved'", (video_id,))
            if not cur.fetchone():
                return jsonify({"ok": False, "error": "Video not found."}), 404
            cur.execute(
                "INSERT INTO social_reports (video_id,reporter_id,reason) VALUES (%s,%s,%s)",
                (video_id, viewer["id"], reason),
            )
        conn.commit()
    return jsonify({"ok": True, "message": "Report sent to Nightfall moderators."})


@app.get("/admin/community")
def admin_community():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    if not DATABASE_URL:
        return render_template("admin_community.html", videos=[], reports=[], error="Community storage is not configured. Add DATABASE_URL in Render.")
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id,discord_id,username,avatar_url,video_url,title,description,status,strikes,created_at FROM social_videos ORDER BY id DESC LIMIT 200")
                videos=[{"id":r[0],"discord_id":r[1],"username":r[2],"avatar_url":r[3],"video_url":r[4],"title":r[5],"description":r[6],"status":r[7],"strikes":r[8],"created_at":r[9].isoformat() if hasattr(r[9],"isoformat") else str(r[9])} for r in cur.fetchall()]
                cur.execute("SELECT id,video_id,reporter_id,reason,status,created_at FROM social_reports WHERE status='open' ORDER BY id DESC")
                reports=[{"id":r[0],"video_id":r[1],"reporter_id":r[2],"reason":r[3],"status":r[4],"created_at":r[5].isoformat() if hasattr(r[5],"isoformat") else str(r[5])} for r in cur.fetchall()]
        return render_template("admin_community.html",videos=videos,reports=reports)
    except psycopg.Error:
        app.logger.exception("Could not load Community moderation data")
        return render_template("admin_community.html",videos=[],reports=[],error="Could not load Community moderation data right now.")

@app.post("/admin/community/video/<int:video_id>/<action>")
def admin_community_video(video_id, action):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    if action not in {"approve","delete","strike"}:
        return "Unknown action.", 400
    if not DATABASE_URL:
        return "Community storage is not configured. Add DATABASE_URL in Render.", 503
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT discord_id,strikes,status FROM social_videos WHERE id=%s FOR UPDATE", (video_id,))
                row=cur.fetchone()
                if not row:
                    return "Video not found.", 404
                if action=="approve":
                    cur.execute("UPDATE social_videos SET status='approved' WHERE id=%s", (video_id,))
                elif action=="delete":
                    cur.execute("UPDATE social_videos SET status='removed' WHERE id=%s", (video_id,))
                else:
                    new_strikes = int(row[1] or 0) + 1
                    cur.execute("UPDATE social_videos SET strikes=%s,status='removed' WHERE id=%s", (new_strikes, video_id))
                    if new_strikes >= 3:
                        cur.execute("UPDATE social_videos SET status='blocked' WHERE discord_id=%s", (row[0],))
                cur.execute("UPDATE social_reports SET status='resolved' WHERE video_id=%s", (video_id,))
            conn.commit()
    except psycopg.Error:
        app.logger.exception("Could not moderate Community video %s", video_id)
        return "Could not update that video right now.", 500
    return redirect(url_for("admin_community"))

@app.post("/admin/community/report/<int:report_id>/resolve")
def admin_community_report(report_id):
    if not session.get("admin"): return redirect(url_for("admin_login"))
    with db_connect() as conn:
        conn.execute("UPDATE social_reports SET status='resolved' WHERE id=%s",(report_id,))
        conn.commit()
    return redirect(url_for("admin_community"))

@app.post("/admin/support/<int:ticket_id>/close")
def admin_support_close(ticket_id):
    if not session.get("admin"): return redirect(url_for("admin_login"))
    if DATABASE_URL:
        with db_connect() as conn:
            conn.execute("UPDATE support_tickets SET status='closed', updated_at=NOW() WHERE id=%s",(ticket_id,))
            conn.commit()
    else:
        for t in session.get("support_tickets",[]):
            if int(t.get("id",0)) == ticket_id: t["status"]="closed"
        session.modified=True
    return redirect(url_for("admin_support"))

@app.post("/api/support/ai")
def support_ai():
    payload=request.get_json(silent=True) or {}
    message=str(payload.get("message") or "").strip()[:2000]
    if not message: return jsonify({"ok":False,"error":"Write a message first."}),400
    key=os.getenv("OPENROUTER_API_KEY","").strip()
    if not key:
        return jsonify({"ok":True,"answer":"AI is not connected yet. You can still open Talk to an Admin and send a real support ticket."})
    model=os.getenv("OPENROUTER_TEXT_MODEL","openrouter/free")
    try:
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","HTTP-Referer":request.host_url,"X-Title":"Nightfall Support"},json={"model":model,"messages":[{"role":"system","content":"You are Nightfall's website support assistant. Answer the user's actual question instead of giving a generic fallback. Help with Nightfall Discord commands, setup, moderation, tickets, Premium, website features, and troubleshooting. Be concise and honest. Never request passwords, tokens, API keys, or private credentials. If the issue requires admin access, explain that the user can open a human support ticket on the same Support page."},{"role":"user","content":message}]},timeout=20)
        data=r.json()
        answer=((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not answer: raise ValueError("empty")
        return jsonify({"ok":True,"answer":str(answer)[:5000]})
    except Exception:
        return jsonify({"ok":True,"answer":"The AI service could not answer that right now. Open Talk to an Admin on this page and send the problem as a support ticket."})

@app.route("/suggestions", methods=["GET","POST"])
def suggestions():
    if request.method == "POST":
        name = (request.form.get("name") or "Anonymous").strip()[:40] or "Anonymous"
        suggestion = (request.form.get("suggestion") or "").strip()[:1000]
        if not suggestion:
            return render_template("suggestions.html", error="Please write a suggestion.")
        date = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
        if DATABASE_URL:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO suggestions (name, suggestion, date) VALUES (%s, %s, %s)", (name, suggestion, date))
                conn.commit()
        else:
            items = session.get("suggestions", [])
            items.insert(0, {"name": name, "suggestion": suggestion, "date": date})
            session["suggestions"] = items[:50]
        return render_template("suggestions.html", submitted=True)
    return render_template("suggestions.html")

@app.get("/suggestions/list")
def suggestion_list():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    if DATABASE_URL:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, suggestion, date FROM suggestions ORDER BY id DESC")
                items = [{"id":r[0],"name":r[1],"suggestion":r[2],"date":r[3]} for r in cur.fetchall()]
    else:
        items = session.get("suggestions", [])
    return render_template("suggestions_list.html", suggestions=items)



REVIEW_BAD_WORDS = {"fuck","fucking","shit","bitch","cunt","nigger","nigga","retard","retarded","kys"}
def review_is_clean(text_value):
    words = {w.lower() for w in __import__("re").findall(r"[a-zA-Z0-9']+", text_value)}
    return not bool(words & REVIEW_BAD_WORDS)

@app.get("/api/reviews")
def get_reviews():
    if not DATABASE_URL:
        return jsonify({"ok": True, "reviews": []})
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name, rating, review, date FROM reviews WHERE approved = TRUE ORDER BY id DESC LIMIT 50")
                rows = cur.fetchall()
        return jsonify({"ok": True, "reviews": [{"name": r[0], "rating": r[1], "review": r[2], "date": r[3]} for r in rows]})
    except psycopg.Error as exc:
        app.logger.warning("Could not load reviews: %s", type(exc).__name__)
        return jsonify({"ok": False, "reviews": []}), 500

@app.post("/api/reviews")
def post_review():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "Anonymous").strip()[:40] or "Anonymous"
    review = str(payload.get("review") or "").strip()[:500]
    try: rating = int(payload.get("rating", 5))
    except (TypeError, ValueError): rating = 0
    if not review: return jsonify({"ok": False, "error": "Please write a review."}), 400
    if rating not in {1,2,3,4,5}: return jsonify({"ok": False, "error": "Choose a rating from 1 to 5."}), 400
    if not review_is_clean(review) or not review_is_clean(name):
        return jsonify({"ok": False, "error": "That review was filtered. Please keep it respectful."}), 400
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Reviews are temporarily unavailable."}), 503
    date = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO reviews (name, rating, review, date, approved) VALUES (%s, %s, %s, %s, TRUE)", (name, rating, review, date))
            conn.commit()
        return jsonify({"ok": True})
    except psycopg.Error as exc:
        app.logger.warning("Could not save review: %s", type(exc).__name__)
        return jsonify({"ok": False, "error": "Could not save your review right now."}), 500



@app.get("/api/bot/status")
def bot_status():
    return jsonify({"ok": True, "online": bot_online()})

@app.get("/commands")
def commands():
    return render_template("commands.html", commands=all_commands())


@app.get("/guidelines")
def guidelines():
    return render_template("guidelines.html")


@app.get("/announcements")
def announcements():
    items = load_announcements()
    return render_template(
        "announcements.html",
        announcements=items,
        site_updates=[item for item in items if item.get("kind") != "bot"],
        bot_updates=[item for item in items if item.get("kind") == "bot"],
    )


@app.get("/login")
def login():
    if not DISCORD_CLIENT_ID or not DISCORD_REDIRECT_URI:
        return "Discord OAuth is not configured yet. Add DISCORD_CLIENT_ID and DISCORD_REDIRECT_URI in Render.", 500
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "prompt": "consent",
    }
    return redirect(f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}")


@app.get("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    token = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        },
        timeout=12,
    )
    if token.status_code != 200:
        return f"Discord login failed: {token.text}", 400

    token_data = token.json()
    session["access_token"] = token_data["access_token"]
    session["refresh_token"] = token_data.get("refresh_token", "")
    session["token_expires_at"] = time.time() + int(token_data.get("expires_in", 604800))
    session.permanent = True
    session.modified = True
    award_site_xp("login", 25)

    me = requests.get(f"{DISCORD_API}/users/@me", headers=discord_headers(), timeout=12)
    if me.status_code != 200:
        session.clear()
        return "Could not read your Discord profile.", 400

    session["user"] = me.json()
    return redirect(request.args.get("next") or url_for("servers"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/servers")
@login_required
def servers():
    r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
    if r.status_code != 200:
        session.clear()
        return redirect(url_for("login"))
    guilds = [
        g for g in r.json()
        if ((int(g.get("permissions", "0")) & MANAGE_GUILD) == MANAGE_GUILD or (int(g.get("permissions", "0")) & ADMINISTRATOR) == ADMINISTRATOR)
    ]
    bot_guilds = bot_guild_snapshot()
    bot_ids = {str(x["id"]) for x in bot_guilds} if bot_online() else set()

    for guild in guilds:
        guild["bot_present"] = str(guild["id"]) in bot_ids
        icon_hash = guild.get("icon")
        guild["icon_url"] = (
            f"https://cdn.discordapp.com/icons/{guild['id']}/{icon_hash}.png?size=128"
            if icon_hash else ""
        )

    bot_api_error = None if bot_online() else "Nightfall has not checked in with the website yet. Make sure the bot and bridge secret are configured."

    return render_template(
        "servers.html",
        guilds=guilds,
        bot_api_error=bot_api_error,
    )


@app.get("/dashboard/<guild_id>")
@login_required
def dashboard(guild_id):
    guilds_r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
    if guilds_r.status_code != 200:
        return redirect(url_for("login"))
    guild = next((g for g in guilds_r.json() if g["id"] == guild_id), None)
    if not guild:
        return "You do not have permission to manage this server.", 403
    permissions = int(guild.get("permissions", "0"))
    if not ((permissions & MANAGE_GUILD) == MANAGE_GUILD or (permissions & ADMINISTRATOR) == ADMINISTRATOR):
        return "You do not have permission to manage this server.", 403

    guild_icon_hash = guild.get("icon")
    guild["icon_url"] = f"https://cdn.discordapp.com/icons/{guild_id}/{guild_icon_hash}.png?size=128" if guild_icon_hash else ""
    bot_guild = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), None)
    settings = bot_guild.get("settings", {}) if bot_guild else {}
    bot_error = None if bot_online() and bot_guild else "Nightfall is offline or is not connected to this server."

    # Compact live server metrics for the control center.
    enabled_security = sum(bool(settings.get(key)) for key in ("anti_raid", "anti_nuke", "anti_link"))
    enabled_community = sum(bool(settings.get(key)) for key in ("welcome_channel_id", "leave_channel_id", "autorole_id", "booster_role_id", "vouch_channel_id", "feedback_channel_id"))
    enabled_support = sum(bool(settings.get(key)) for key in ("ticket_panel_channel_id", "ticket_category_id", "jail_enabled", "jail_appeal_channel_id"))
    dashboard_stats = {
        "members": int(guild.get("approximate_member_count") or guild.get("member_count") or (bot_guild or {}).get("member_count") or 0),
        "security": enabled_security,
        "community": enabled_community,
        "support": enabled_support,
        "prefix": settings.get("prefix", "!"),
        "bot_online": bot_online() and bool(bot_guild),
    }
    return render_template(
        "dashboard.html",
        guild=guild,
        settings=settings,
        bot_error=bot_error,
        setting_groups=SETTING_GROUPS,
        dashboard_stats=dashboard_stats,
    )


@app.post("/api/dashboard/<guild_id>/settings")
@login_required
def update_settings(guild_id):
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not bot_online() or not any(item["id"] == str(guild_id) for item in bot_guild_snapshot()):
        return jsonify({"ok": False, "error": "Nightfall is offline or is not connected to this server."}), 503
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return jsonify({"ok": False, "error": "Choose at least one setting to update."}), 400
    clean = {}
    for key, value in payload.items():
        if key not in EDITABLE_SETTINGS:
            return jsonify({"ok": False, "error": f"Unsupported setting: {key}."}), 400
        if key in CHANNEL_SETTINGS | ROLE_SETTINGS | {"appeal_server_id"}:
            raw = str(value or "").strip()
            if raw and (not raw.isdigit() or len(raw) > 22):
                return jsonify({"ok": False, "error": f"{key.replace('_', ' ')} must be a numeric Discord ID."}), 400
            clean[key] = int(raw) if raw else None
        elif key in TOGGLE_SETTINGS:
            if not isinstance(value, bool):
                return jsonify({"ok": False, "error": f"{key.replace('_', ' ')} must be on or off."}), 400
            clean[key] = value
        elif key == "prefix":
            raw = str(value).strip()
            if not 1 <= len(raw) <= 5:
                return jsonify({"ok": False, "error": "Prefix must contain 1–5 characters."}), 400
            clean[key] = raw
        elif key == "ticket_questions":
            if not isinstance(value, dict) or len(value) > 10 or any(not isinstance(k, str) or not isinstance(v, list) or len(v) > 5 or any(not isinstance(q, str) or len(q) > 300 for q in v) for k, v in value.items()):
                return jsonify({"ok": False, "error": "Ticket questions must be a JSON object with up to five short questions per ticket type."}), 400
            clean[key] = value
        elif key == "ticket_options":
            if not isinstance(value, list) or not 1 <= len(value) <= 10:
                return jsonify({"ok": False, "error": "Add between 1 and 10 ticket options."}), 400
            options = [str(x).strip().lower()[:40] for x in value if str(x).strip()]
            if not options:
                return jsonify({"ok": False, "error": "Ticket options cannot be empty."}), 400
            clean[key] = options
        elif key == "appeal_invite_url":
            raw = str(value).strip()
            parsed = urlparse(raw) if raw else None
            if raw and not (parsed.scheme == "https" and parsed.netloc.lower() in {"discord.gg", "discord.com"} and (parsed.netloc.lower() == "discord.gg" or parsed.path.startswith("/invite/"))):
                return jsonify({"ok": False, "error": "Use a valid HTTPS Discord invite URL."}), 400
            clean[key] = raw
        else:
            raw = str(value).strip()
            if key == "autoreaction_emoji" and len(raw) > 50:
                return jsonify({"ok": False, "error": "Emoji value is too long."}), 400
            clean[key] = raw
    job_id = queue_bot_job(guild_id, "settings", clean)
    return jsonify({"ok": True, "queued": True, "job_id": job_id})


@app.post("/api/dashboard/<guild_id>/action")
@login_required
def dashboard_action(guild_id):
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not bot_online() or not any(item["id"] == str(guild_id) for item in bot_guild_snapshot()):
        return jsonify({"ok": False, "error": "Nightfall is offline or is not connected to this server."}), 503
    payload = request.get_json(silent=True) or {}
    allowed_actions = {"sync_setup", "post_ticket_panel", "post_verification_panel", "post_feedback_panel", "post_application_panel", "toggle_jail"}
    if payload.get("action") not in allowed_actions:
        return jsonify({"ok": False, "error": "Unknown action."}), 400
    guild_snapshot = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {})
    settings = guild_snapshot.get("settings", {})
    required = {
        "post_ticket_panel": ("ticket_panel_channel_id", "Set a ticket panel channel in Tickets & appeals first."),
        "post_verification_panel": ("verification_channel_id", "Set a verification channel in Security first."),
        "post_feedback_panel": ("feedback_channel_id", "Set a feedback channel in Community first."),
        "post_application_panel": ("staff_application_channel_id", "Set an applications channel in Community first."),
    }
    if payload["action"] in required and not settings.get(required[payload["action"]][0]):
        return jsonify({"ok": False, "error": required[payload["action"]][1]}), 400
    job_id = queue_bot_job(guild_id, "action", payload)
    return jsonify({"ok": True, "queued": True, "job_id": job_id})


@app.get("/premium")
@login_required
def premium_vault():
    link = get_roblox_link(current_discord_user_id())
    return render_template("premium.html", link=link, premium_active=roblox_premium_active(link))

@app.post("/api/premium/link/start")
@login_required
def premium_link_start():
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Premium linking requires the shared database."}), 503
    discord_id = current_discord_user_id()
    token = secrets.token_hex(4).upper()
    with db_connect() as conn:
        conn.execute(
            "INSERT INTO roblox_links(discord_id,link_token) VALUES(%s,%s) "
            "ON CONFLICT(discord_id) DO UPDATE SET link_token=EXCLUDED.link_token, token_created_at=NOW(), updated_at=NOW()",
            (discord_id, token),
        )
        conn.commit()
    return jsonify({"ok": True, "code": token, "expires_minutes": 15})

@app.post("/api/roblox/link/claim")
def roblox_link_claim():
    if not ROBLOX_BRIDGE_SECRET:
        return jsonify({"ok": False, "error": "Roblox bridge is not configured."}), 503
    supplied = request.headers.get("X-Roblox-Bridge-Key", "")
    if not compare_digest(supplied, ROBLOX_BRIDGE_SECRET):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("code") or "").strip().upper()
    roblox_user_id = str(payload.get("roblox_user_id") or "").strip()
    if not token or not roblox_user_id.isdigit():
        return jsonify({"ok": False, "error": "Invalid linking data."}), 400
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Shared database unavailable."}), 503
    with db_connect() as conn:
        row = conn.execute(
            "SELECT discord_id FROM roblox_links WHERE link_token=%s AND token_created_at > NOW() - INTERVAL '15 minutes'",
            (token,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "That link code is invalid or expired."}), 404
        discord_id = str(row[0])
        conn.execute(
            "UPDATE roblox_links SET roblox_user_id=%s, link_token=%s, updated_at=NOW() WHERE discord_id=%s",
            (roblox_user_id, secrets.token_hex(16), discord_id),
        )
        conn.commit()
    return jsonify({"ok": True, "discord_id": discord_id})

@app.post("/api/roblox/premium-sync")
def roblox_premium_sync():
    if not ROBLOX_BRIDGE_SECRET:
        return jsonify({"ok": False, "error": "Roblox bridge is not configured."}), 503
    supplied = request.headers.get("X-Roblox-Bridge-Key", "")
    if not compare_digest(supplied, ROBLOX_BRIDGE_SECRET):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    roblox_user_id = str(payload.get("roblox_user_id") or "").strip()
    if not roblox_user_id.isdigit():
        return jsonify({"ok": False, "error": "Invalid Roblox user ID."}), 400
    premium = bool(payload.get("premium"))
    source = str(payload.get("source") or "none")[:30]
    expires_at = float(payload.get("expires_at") or 0)
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Shared database unavailable."}), 503
    with db_connect() as conn:
        row = conn.execute("SELECT discord_id FROM roblox_links WHERE roblox_user_id=%s", (roblox_user_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Roblox account is not linked to a Nightfall Discord account."}), 404
        conn.execute(
            "UPDATE roblox_links SET premium=%s, premium_source=%s, premium_expires_at=%s, updated_at=NOW() WHERE roblox_user_id=%s",
            (premium, source, expires_at, roblox_user_id),
        )
        conn.commit()
    return jsonify({"ok": True, "premium": premium, "source": source, "expires_at": expires_at})

@app.get("/api/premium/servers")
@login_required
def premium_servers():
    link = get_roblox_link(current_discord_user_id())
    if not roblox_premium_active(link):
        return jsonify({"ok": False, "error": "Premium is required to open the Vault."}), 403
    try:
        response = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
        if response.status_code != 200:
            return jsonify({"ok": False, "error": "Could not read your Discord servers."}), 502
        manageable = []
        for guild in response.json():
            permissions = int(guild.get("permissions", "0"))
            if not (permissions & MANAGE_GUILD or permissions & ADMINISTRATOR):
                continue
            gid = str(guild.get("id"))
            if any(item["id"] == gid for item in bot_guild_snapshot()):
                manageable.append({"id": gid, "name": guild.get("name", "Unknown server")})
        return jsonify({"ok": True, "servers": manageable})
    except (requests.RequestException, ValueError, TypeError):
        return jsonify({"ok": False, "error": "Could not read your Discord servers."}), 502

@app.get("/api/premium/status")
@login_required
def premium_status():
    link = get_roblox_link(current_discord_user_id())
    return jsonify({"ok": True, "linked": bool(link and link.get("roblox_user_id")), "premium": roblox_premium_active(link), "source": (link or {}).get("premium_source", "none"), "expires_at": (link or {}).get("premium_expires_at", 0)})

@app.get("/api/premium/vault/<guild_id>")
@login_required
def premium_vault_data(guild_id):
    link = get_roblox_link(current_discord_user_id())
    if not roblox_premium_active(link):
        return jsonify({"ok": False, "error": "Premium is required to open the Vault."}), 403
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not bot_online() or not any(item["id"] == str(guild_id) for item in bot_guild_snapshot()):
        return jsonify({"ok": False, "error": "Nightfall is offline or is not connected to this server."}), 503
    snapshot = next(item for item in bot_guild_snapshot() if item["id"] == str(guild_id))
    return jsonify({"ok": True, "guild": {"id": str(guild_id), "name": snapshot.get("name", ""), "settings": snapshot.get("settings", {})}})

@app.post("/api/premium/vault/<guild_id>/command")
@login_required
def premium_vault_command(guild_id):
    link = get_roblox_link(current_discord_user_id())
    if not roblox_premium_active(link):
        return jsonify({"ok": False, "error": "Premium is required to use the Vault."}), 403
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not bot_online() or not any(item["id"] == str(guild_id) for item in bot_guild_snapshot()):
        return jsonify({"ok": False, "error": "Nightfall is offline or is not connected to this server."}), 503
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or "").strip().lower()
    allowed = {"ping","membercount","ban","kick","warn","purge","warnings","clearwarnings","announce","poll","timeout","lock","unlock","slowmode","afk","jail","unjail","setup","ticket","ticket_panel","ticket_questions","appeal_server","appeal_group","autoreaction","role_give","role_make","reset_invites","invites","invited","inviter","ai_ask","ai_story","ai_roast","ai_compliment","ai_riddle","ai_poem","ai_joke","ai_caption","ai_namegen","ai_quiz","aiimage","roleinfo","channelinfo"}
    if command not in allowed:
        return jsonify({"ok": False, "error": "That command is not available through the Vault."}), 400
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    job_id = queue_bot_job(guild_id, "vault_command", {"command": command, "args": args, "discord_id": current_discord_user_id()})
    return jsonify({"ok": True, "queued": True, "job_id": job_id})

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "Nightfall Dashboard"})



ACHIEVEMENTS = [
    ("first_steps", "🌱 First Steps", "Earn your first 100 XP.", 100),
    ("night_walker", "🌙 Night Walker", "Reach level 5.", 500),
    ("veteran", "⭐ Nightfall Veteran", "Reach 10,000 XP.", 10000),
    ("secret_hunter", "🥚 Secret Hunter", "Discover 10 Nightfall secrets.", 0),
    ("arcade_regular", "🎮 Arcade Regular", "Submit an Arcade score.", 0),
    ("social", "💬 Social Night", "Leave your first Community comment.", 0),
    ("popular", "👥 Night Circle", "Reach 5 followers.", 0),
]
DAILY_CHALLENGES = [
    ("arcade", "Play an Arcade game", "Submit an Arcade score today.", 50),
    ("community", "Visit Community", "Open the Community feed today.", 25),
    ("leaderboard", "Check the rankings", "Visit the global leaderboard today.", 15),
]
def daily_challenge():
    import datetime as _dt
    day = _dt.date.today().toordinal()
    return DAILY_CHALLENGES[day % len(DAILY_CHALLENGES)]

def sync_achievements():
    user=current_site_user()
    if not user or not DATABASE_URL: return
    try:
        with db_connect() as conn:
            xp_row=conn.execute("SELECT xp FROM site_profiles WHERE discord_id=%s",(user["id"],)).fetchone()
            xp=int(xp_row[0]) if xp_row else 0
            scores=conn.execute("SELECT COUNT(*) FROM arcade_scores WHERE discord_id=%s",(user["id"],)).fetchone()[0]
            comments=conn.execute("SELECT COUNT(*) FROM social_comments WHERE discord_id=%s AND status='approved'",(user["id"],)).fetchone()[0]
            followers=conn.execute("SELECT COUNT(*) FROM social_follows WHERE following_id=%s",(user["id"],)).fetchone()[0]
            unlocked=[]
            if xp>=100: unlocked.append("first_steps")
            if xp>=500: unlocked.append("night_walker")
            if xp>=10000: unlocked.append("veteran")
            if scores: unlocked.append("arcade_regular")
            if comments: unlocked.append("social")
            if followers>=5: unlocked.append("popular")
            for key in unlocked:
                conn.execute("INSERT INTO site_achievements(discord_id,achievement) VALUES(%s,%s) ON CONFLICT DO NOTHING",(user["id"],key))
            conn.commit()
    except psycopg.Error as exc:
        app.logger.warning("Could not sync achievements: %s", type(exc).__name__)

@app.get("/achievements")
def achievements():
    sync_achievements()
    unlocked=set()
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT achievement FROM site_achievements WHERE discord_id=%s",(current_site_user()["id"],))
                    unlocked={r[0] for r in cur.fetchall()}
        except psycopg.Error: pass
    return render_template("achievements.html", achievements=[{"key":k,"name":n,"desc":d,"unlocked":k in unlocked} for k,n,d,_ in ACHIEVEMENTS])

@app.get("/daily")
def daily():
    key,title,desc,reward=daily_challenge()
    return render_template("daily.html", key=key,title=title,description=desc,reward=reward)

@app.post("/api/daily/claim")
def claim_daily():
    user=current_site_user()
    key,title,desc,reward=daily_challenge()
    if not DATABASE_URL: return jsonify({"ok":False,"error":"Daily storage unavailable."}),503
    import datetime as _dt
    today=_dt.date.today().isoformat()
    with db_connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS daily_completions(discord_id TEXT NOT NULL, challenge_date DATE NOT NULL, challenge_key TEXT NOT NULL, completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(discord_id,challenge_date,challenge_key))")
        done=conn.execute("SELECT 1 FROM daily_completions WHERE discord_id=%s AND challenge_date=%s AND challenge_key=%s",(user["id"],today,key)).fetchone()
        if done: return jsonify({"ok":True,"message":"Today's challenge is already complete."})
        eligible=False
        if key=="arcade": eligible=conn.execute("SELECT 1 FROM arcade_scores WHERE discord_id=%s AND created_at::date=CURRENT_DATE LIMIT 1",(user["id"],)).fetchone() is not None
        elif key=="community": eligible=bool(session.get("daily_community_visit"))
        elif key=="leaderboard": eligible=bool(session.get("daily_leaderboard_visit"))
        if not eligible: return jsonify({"ok":False,"error":"Complete the challenge first."}),400
        conn.execute("INSERT INTO daily_completions(discord_id,challenge_date,challenge_key) VALUES(%s,%s,%s)",(user["id"],today,key)); conn.commit()
    award_site_xp("daily_"+key,reward); sync_achievements()
    return jsonify({"ok":True,"message":f"Challenge complete: +{reward} XP."})

@app.post("/api/profile")
def update_profile():
    payload=request.get_json(silent=True) or {}
    bio=str(payload.get("bio") or "").strip()[:160]
    theme=str(payload.get("theme") or "default").strip()[:30]
    title=str(payload.get("title") or "").strip()[:40]
    allowed_themes={"default","midnight","nebula","ember"}
    if theme not in allowed_themes: theme="default"
    if not DATABASE_URL: return jsonify({"ok":False,"error":"Profile storage is unavailable."}),503
    user=current_site_user()
    with db_connect() as conn:
        conn.execute("INSERT INTO site_settings (discord_id,bio,theme,title) VALUES (%s,%s,%s,%s) ON CONFLICT (discord_id) DO UPDATE SET bio=EXCLUDED.bio,theme=EXCLUDED.theme,title=EXCLUDED.title",(user["id"],bio,theme,title))
        conn.commit()
    return jsonify({"ok":True})

def current_site_user():
    user = session.get("user") or {}
    uid = str(user.get("id") or "")
    if not uid:
        return None
    avatar = str(user.get("avatar_url") or "")
    if not avatar and user.get("avatar"):
        avatar = f"https://cdn.discordapp.com/avatars/{uid}/{user['avatar']}.png?size=128"
    return {"id": uid, "username": str(user.get("global_name") or user.get("username") or "Discord user"), "avatar_url": avatar}

def site_level(xp):
    return max(1, int(xp // 100) + 1)

def site_badges(xp):
    badges = []
    if xp >= 100: badges.append(("🌙", "Night Walker", "Reach 100 XP."))
    if xp >= 500: badges.append(("⭐", "Nightfall Veteran", "Reach 500 XP."))
    if xp >= 1000: badges.append(("👑", "Nightfall Legend", "Reach 1,000 XP."))
    return badges

def award_site_xp(action, amount=10):
    user = current_site_user()
    if not user or not DATABASE_URL:
        return
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO site_profiles (discord_id, username, avatar_url) VALUES (%s,%s,%s) ON CONFLICT (discord_id) DO UPDATE SET username=EXCLUDED.username, avatar_url=EXCLUDED.avatar_url, last_seen=NOW()", (user["id"], user["username"], user["avatar_url"]))
                cur.execute("INSERT INTO site_xp_events (discord_id, action) VALUES (%s,%s) ON CONFLICT (discord_id, action) DO UPDATE SET last_awarded=NOW() WHERE site_xp_events.last_awarded < NOW() - INTERVAL '1 hour' RETURNING discord_id", (user["id"], action))
                if cur.fetchone():
                    cur.execute("UPDATE site_profiles SET xp=xp+%s,last_seen=NOW() WHERE discord_id=%s", (amount, user["id"]))
            conn.commit()
    except psycopg.Error as exc:
        app.logger.warning("Could not award site XP: %s", type(exc).__name__)

@app.get("/profile")
def profile():
    sync_achievements()
    user=current_site_user()
    xp=0; rank=None; followers=0; following=0; scores=[]
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT xp FROM site_profiles WHERE discord_id=%s", (user["id"],)); row=cur.fetchone(); xp=int(row[0]) if row else 0
                    cur.execute("SELECT COUNT(*) FROM social_follows WHERE following_id=%s", (user["id"],)); followers=int(cur.fetchone()[0])
                    cur.execute("SELECT COUNT(*) FROM social_follows WHERE follower_id=%s", (user["id"],)); following=int(cur.fetchone()[0])
                    cur.execute("SELECT COUNT(*)+1 FROM site_profiles WHERE xp > %s", (xp,)); rank=int(cur.fetchone()[0])
                    cur.execute("SELECT game, MAX(score) FROM arcade_scores WHERE discord_id=%s GROUP BY game ORDER BY MAX(score) DESC LIMIT 10", (user["id"],)); scores=[{"game":r[0],"score":r[1]} for r in cur.fetchall()]
        except psycopg.Error as exc:
            app.logger.warning("Could not load profile: %s", type(exc).__name__)
    bio=""; theme="default"; title=""
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row=conn.execute("SELECT bio,theme,title FROM site_settings WHERE discord_id=%s",(user["id"],)).fetchone()
                if row: bio,theme,title=row
        except psycopg.Error: pass
    return render_template("profile.html", user=user, xp=xp, level=site_level(xp), rank=rank, followers=followers, following=following, badges=site_badges(xp), scores=scores, bio=bio, theme=theme, title=title)

@app.get("/u/<discord_id>")
def public_profile(discord_id):
    if not DATABASE_URL:
        return "Profiles are unavailable right now.", 503
    try:
        with db_connect() as conn:
            user_row=conn.execute("SELECT username,avatar_url,xp FROM site_profiles WHERE discord_id=%s",(str(discord_id),)).fetchone()
            if not user_row:
                return "Profile not found.",404
            settings=conn.execute("SELECT bio,theme,title FROM site_settings WHERE discord_id=%s",(str(discord_id),)).fetchone()
            scores=conn.execute("SELECT game,MAX(score) FROM arcade_scores WHERE discord_id=%s GROUP BY game ORDER BY MAX(score) DESC LIMIT 10",(str(discord_id),)).fetchall()
            followers=conn.execute("SELECT COUNT(*) FROM social_follows WHERE following_id=%s",(str(discord_id),)).fetchone()[0]
            following=conn.execute("SELECT COUNT(*) FROM social_follows WHERE follower_id=%s",(str(discord_id),)).fetchone()[0]
        return render_template("public_profile.html", user={"id":str(discord_id),"username":user_row[0],"avatar_url":user_row[1]}, xp=int(user_row[2]), level=site_level(user_row[2]), bio=settings[0] if settings else "", theme=settings[1] if settings else "default", title=settings[2] if settings else "", scores=[{"game":x[0],"score":x[1]} for x in scores], followers=int(followers), following=int(following), badges=site_badges(user_row[2]))
    except psycopg.Error as exc:
        app.logger.warning("Could not load public profile: %s", type(exc).__name__)
        return "Profile unavailable.",503

@app.get("/nightfall-passport")
def nightfall_passport():
    user=current_site_user(); sync_achievements()
    xp=0; streak=0; achievements=[]; scores=[]; reputation=0
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row=conn.execute("SELECT xp FROM site_profiles WHERE discord_id=%s",(user["id"],)).fetchone(); xp=int(row[0]) if row else 0
                st=conn.execute("SELECT streak FROM site_settings WHERE discord_id=%s",(user["id"],)).fetchone(); streak=int(st[0]) if st else 0
                achievements=[x[0] for x in conn.execute("SELECT achievement FROM site_achievements WHERE discord_id=%s ORDER BY unlocked_at",(user["id"],)).fetchall()]
                scores=[{"game":x[0],"score":x[1]} for x in conn.execute("SELECT game,MAX(score) FROM arcade_scores WHERE discord_id=%s GROUP BY game ORDER BY MAX(score) DESC",(user["id"],)).fetchall()]
                rep=conn.execute("SELECT score FROM site_reputation WHERE discord_id=%s",(user["id"],)).fetchone(); reputation=int(rep[0]) if rep else 0
        except psycopg.Error as exc:
            app.logger.warning("Could not load passport: %s", type(exc).__name__)
    return render_template("passport.html",user=user,xp=xp,level=site_level(xp),streak=streak,achievements=achievements,scores=scores,reputation=reputation)

@app.get("/leaderboards")
def leaderboards():
    session["daily_leaderboard_visit"]=True
    rows=[]
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT discord_id,username,xp FROM site_profiles ORDER BY xp DESC,created_at ASC LIMIT 100")
                    rows=[{"discord_id":r[0],"username":r[1],"xp":r[2],"level":site_level(r[2])} for r in cur.fetchall()]
        except psycopg.Error as exc:
            app.logger.warning("Could not load XP leaderboard: %s", type(exc).__name__)
    arcade=[]
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                games=["coin","guess","reaction","tap","memory","trivia","math","word","stars","pattern"]
                for game in games:
                    top=conn.execute("SELECT username,discord_id,MAX(score) FROM arcade_scores WHERE game=%s GROUP BY username,discord_id ORDER BY MAX(score) DESC LIMIT 10",(game,)).fetchall()
                    arcade.append({"game":game,"rows":[{"username":x[0],"discord_id":x[1],"score":x[2]} for x in top]})
        except psycopg.Error as exc:
            app.logger.warning("Could not load Arcade leaderboards: %s", type(exc).__name__)
    return render_template("leaderboards.html", rows=rows, arcade=arcade)

@app.get("/api/social/video/<int:video_id>/likes")
def social_likes(video_id):
    if not DATABASE_URL: return jsonify({"ok":True,"likes":0,"liked":False})
    user=current_site_user()
    with db_connect() as conn:
        likes=conn.execute("SELECT COUNT(*) FROM social_likes WHERE video_id=%s",(video_id,)).fetchone()[0]
        liked=conn.execute("SELECT 1 FROM social_likes WHERE video_id=%s AND discord_id=%s",(video_id,user["id"])).fetchone() is not None
    return jsonify({"ok":True,"likes":int(likes),"liked":liked})

@app.post("/api/social/like/<int:video_id>")
def social_like(video_id):
    if not DATABASE_URL: return jsonify({"ok":False,"error":"Storage unavailable."}),503
    user=current_site_user()
    with db_connect() as conn:
        exists=conn.execute("SELECT 1 FROM social_likes WHERE video_id=%s AND discord_id=%s",(video_id,user["id"])).fetchone()
        if exists: conn.execute("DELETE FROM social_likes WHERE video_id=%s AND discord_id=%s",(video_id,user["id"]))
        else: conn.execute("INSERT INTO social_likes(video_id,discord_id) VALUES(%s,%s)",(video_id,user["id"]))
        conn.commit()
        count=conn.execute("SELECT COUNT(*) FROM social_likes WHERE video_id=%s",(video_id,)).fetchone()[0]
    return jsonify({"ok":True,"likes":int(count),"liked":not bool(exists)})

@app.get("/api/social/video/<int:video_id>/comments")
def social_comments(video_id):
    if not DATABASE_URL: return jsonify({"ok":True,"comments":[]})
    with db_connect() as conn:
        rows=conn.execute("SELECT username,avatar_url,body,created_at FROM social_comments WHERE video_id=%s AND status='approved' ORDER BY id DESC LIMIT 50",(video_id,)).fetchall()
    return jsonify({"ok":True,"comments":[{"username":x[0],"avatar_url":x[1],"body":x[2],"created_at":str(x[3])} for x in rows]})

@app.post("/api/social/comment/<int:video_id>")
def social_comment(video_id):
    user=current_site_user(); payload=request.get_json(silent=True) or {}; body=str(payload.get("body") or "").strip()[:500]
    if not body: return jsonify({"ok":False,"error":"Comment cannot be empty."}),400
    if not DATABASE_URL: return jsonify({"ok":False,"error":"Storage unavailable."}),503
    with db_connect() as conn:
        conn.execute("INSERT INTO social_comments(video_id,discord_id,username,avatar_url,body) VALUES(%s,%s,%s,%s,%s)",(video_id,user["id"],user["username"],user["avatar_url"],body)); conn.commit()
    award_site_xp("comment",5)
    return jsonify({"ok":True})

@app.get("/notifications")
def notifications():
    items=[]
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id,title,body,read,created_at FROM site_notifications WHERE discord_id=%s ORDER BY id DESC LIMIT 50", (current_site_user()["id"],))
                    items=[{"id":r[0],"title":r[1],"body":r[2],"read":r[3],"created_at":r[4]} for r in cur.fetchall()]
        except psycopg.Error as exc:
            app.logger.warning("Could not load notifications: %s", type(exc).__name__)
    return render_template("notifications.html", notifications=items)

@app.post("/api/notifications/read")
def mark_notifications_read():
    if DATABASE_URL:
        with db_connect() as conn:
            conn.execute("UPDATE site_notifications SET read=TRUE WHERE discord_id=%s", (current_site_user()["id"],))
            conn.commit()
    return jsonify({"ok":True})

@app.post("/api/xp/award")
def api_award_xp():
    payload=request.get_json(silent=True) or {}
    action=str(payload.get("action") or "").strip().lower()
    allowed={"community","arcade","secrets","suggestion","review","profile"}
    if action not in allowed:
        return jsonify({"ok":False,"error":"Unknown XP action."}),400
    award_site_xp(action, 10)
    return jsonify({"ok":True})

def arcade_reward_code():
    return "ducky-squad"


@app.get("/redeem")
@login_required
def redeem():
    user = current_site_user()
    reward = None
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                reward = conn.execute(
                    "SELECT redeemed_at FROM arcade_rewards WHERE discord_id=%s",
                    (user["id"],),
                ).fetchone()
        except psycopg.Error as exc:
            app.logger.warning("Could not load arcade reward: %s", type(exc).__name__)
    return render_template("redeem.html", user=user, reward=reward)

@app.post("/api/arcade/start")
def arcade_start():
    user = current_site_user()
    if not user:
        session["anonymous_arcade"] = {"started_at": time.time(), "hits": 0, "completed": False}
        session.modified = True
        return jsonify({"ok": True, "seconds": 30, "hits": 0, "anonymous": True})
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Reward storage is unavailable."}), 503
    now = time.time()
    with db_connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM arcade_rewards WHERE discord_id=%s",
            (user["id"],),
        ).fetchone()
        if existing:
            return jsonify({"ok": False, "error": "You already completed the secret arcade and claimed your one reward."}), 409
        conn.execute(
            "INSERT INTO arcade_challenges(discord_id,started_at,hits,completed) VALUES(%s,%s,0,FALSE) "
            "ON CONFLICT(discord_id) DO UPDATE SET started_at=EXCLUDED.started_at,hits=0,completed=FALSE",
            (user["id"], now),
        )
        conn.commit()
    return jsonify({"ok": True, "seconds": 30, "hits": 0})

@app.post("/api/arcade/hit")
def arcade_hit():
    user = current_site_user()
    if not user:
        challenge = session.get("anonymous_arcade")
        if not challenge:
            return jsonify({"ok": False, "error": "Start the secret challenge first."}), 400
        if challenge.get("completed"):
            return jsonify({"ok": False, "error": "This challenge is already complete."}), 409
        if time.time() - float(challenge.get("started_at", 0)) > 30:
            session.pop("anonymous_arcade", None)
            return jsonify({"ok": False, "error": "Time expired. Discover the star again to retry."}), 408
        hits = min(10, int(challenge.get("hits", 0)) + 1)
        challenge["hits"] = hits
        session["anonymous_arcade"] = challenge
        session.modified = True
        return jsonify({"ok": True, "hits": hits, "complete": hits >= 10, "anonymous": True})
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Reward storage is unavailable."}), 503
    now = time.time()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT started_at,hits,completed FROM arcade_challenges WHERE discord_id=%s FOR UPDATE",
            (user["id"],),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Start the arcade challenge first."}), 400
        started_at, hits, completed = float(row[0]), int(row[1]), bool(row[2])
        if completed:
            return jsonify({"ok": False, "error": "This challenge has already been completed."}), 409
        if now - started_at > 30:
            return jsonify({"ok": False, "error": "Time expired. You did not earn a code."}), 408
        hits += 1
        if hits > 10:
            hits = 10
        conn.execute("UPDATE arcade_challenges SET hits=%s WHERE discord_id=%s", (hits, user["id"]))
        conn.commit()
    return jsonify({"ok": True, "hits": hits, "complete": hits >= 10})

@app.post("/api/arcade/finish")
def arcade_finish():
    user = current_site_user()
    if not user:
        challenge = session.get("anonymous_arcade")
        if not challenge:
            return jsonify({"ok": False, "error": "Start the secret challenge first."}), 400
        if challenge.get("completed"):
            return jsonify({"ok": False, "error": "This challenge is already complete."}), 409
        if time.time() - float(challenge.get("started_at", 0)) > 30:
            session.pop("anonymous_arcade", None)
            return jsonify({"ok": False, "error": "Time expired. Discover the star again to retry."}), 408
        if int(challenge.get("hits", 0)) < 10:
            return jsonify({"ok": False, "error": "You need 10 hits to finish."}), 400
        challenge["completed"] = True
        session["anonymous_arcade"] = challenge
        session.modified = True
        return jsonify({"ok": True, "anonymous": True, "redeemable": False, "message": "Secret completed! Log in with Discord to redeem the reward."})
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Reward storage is unavailable."}), 503
    now = time.time()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT started_at,hits,completed FROM arcade_challenges WHERE discord_id=%s FOR UPDATE",
            (user["id"],),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Start the arcade challenge first."}), 400
        started_at, hits, completed = float(row[0]), int(row[1]), bool(row[2])
        if completed:
            return jsonify({"ok": False, "error": "You already claimed your arcade reward."}), 409
        if now - started_at > 30:
            return jsonify({"ok": False, "error": "Time expired. Start the challenge again."}), 408
        if hits < 10:
            return jsonify({"ok": False, "error": "You need 10 hits to earn the reward."}), 400
        existing = conn.execute("SELECT 1 FROM arcade_rewards WHERE discord_id=%s", (user["id"],)).fetchone()
        if existing:
            return jsonify({"ok": False, "error": "You already claimed your one arcade reward."}), 409
        code = arcade_reward_code()
        conn.execute(
            "INSERT INTO arcade_rewards(discord_id,code) VALUES(%s,%s)",
            (user["id"], code),
        )
        conn.execute(
            "UPDATE arcade_challenges SET completed=TRUE WHERE discord_id=%s",
            (user["id"],),
        )
        conn.commit()
    return jsonify({
        "ok": True,
        "code": code,
        "discount": 50,
        "message": "Unique one-time 50% off code created for this Discord account."
    })

@app.post("/api/arcade/redeem")
def arcade_redeem():
    user = current_site_user()
    if not user:
        return jsonify({"ok": False, "error": "Discord login required."}), 401
    if not DATABASE_URL:
        return jsonify({"ok": False, "error": "Reward storage is unavailable."}), 503
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip().lower()
    if code != arcade_reward_code():
        return jsonify({"ok": False, "error": "Invalid arcade code."}), 404
    with db_connect() as conn:
        reward = conn.execute(
            "SELECT discord_id,redeemed_at FROM arcade_rewards WHERE code=%s AND discord_id=%s FOR UPDATE",
            (code, user["id"]),
        ).fetchone()
        if not reward:
            return jsonify({"ok": False, "error": "Invalid arcade code."}), 404
        if str(reward[0]) != str(user["id"]):
            return jsonify({"ok": False, "error": "That code belongs to a different Discord account."}), 403
        if reward[1]:
            return jsonify({"ok": False, "error": "This arcade code has already been redeemed."}), 409
        conn.execute(
            "UPDATE arcade_rewards SET redeemed_at=NOW(),redeemed_by=%s WHERE code=%s AND discord_id=%s",
            (user["id"], code, user["id"]),
        )
        conn.commit()
    return jsonify({"ok": True, "discount": 50, "message": "50% Premium discount redeemed successfully. Your discount is now attached to this Discord account."})

@app.post("/api/arcade/score")
def arcade_score():
    payload=request.get_json(silent=True) or {}
    game=str(payload.get("game") or "").strip()[:40]
    try: score=int(payload.get("score",0))
    except (TypeError,ValueError): score=-1
    if not game or score < 0 or score > 100000000:
        return jsonify({"ok":False,"error":"Invalid score."}),400
    if not DATABASE_URL:
        return jsonify({"ok":False,"error":"Leaderboard storage is unavailable."}),503
    user=current_site_user()
    with db_connect() as conn:
        conn.execute("INSERT INTO arcade_scores (discord_id,username,game,score) VALUES (%s,%s,%s,%s)", (user["id"],user["username"],game,score))
        conn.commit()
    award_site_xp("arcade_"+game, 10)
    sync_achievements()
    return jsonify({"ok":True})

COMMANDS = [
    ("!help", "Utility", "Show the bot's command help."),
    ("!about", "Utility", "Show Nightfall's launch description: 1.0v LAUNCH."),
    ("!setup", "Admin tools", "Open the interactive server setup dashboard and configure features there."),
    ("!ban @member [reason]", "Moderation", "Ban a member. Staff only."),
    ("!kick @member [reason]", "Moderation", "Kick a member. Staff only."),
    ("!warn @member [reason]", "Moderation", "Warn a member. Staff only."),
    ("!purge <amount>", "Moderation", "Delete recent messages. Alias: !clear."),
    ("!warnings @member", "Moderation", "Show a member's warning record. Alias: !warns."),
    ("!clearwarnings @member", "Moderation", "Clear a member's warning record. Alias: !resetwarnings."),
    ("!timeout @member <duration> [reason]", "Moderation", "Temporarily timeout a member."),
    ("!lock", "Moderation", "Lock the current channel."),
    ("!unlock", "Moderation", "Unlock the current channel."),
    ("!slowmode <seconds>", "Moderation", "Set channel slowmode. Alias: !slow."),
    ("!jail @member [reason]", "Moderation", "Jail a member using the configured jail system."),
    ("!unjail @member [reason]", "Moderation", "Release a jailed member."),
    ("!announce #channel <message>", "Admin tools", "Post a server announcement."),
    ("!poll <question and options>", "Community", "Create a reaction poll."),
    ("!afk [reason]", "Utility", "Set your AFK status."),
    ("!8ball <question>", "Fun", "Ask the Nightfall 8-Ball a question."),
    ("!mommycount [@member]", "Fun", "Count how many times a member has said “mommy” in this server."),
    ("!swearcount [@member]", "Moderation", "Show the number of configured swear-word matches for a member."),
    ("!antiswear <on|off|status>", "Moderation", "Admins can enable or disable the server's configurable anti-swear filter."),
    ("!swearwords <add|remove|list> [word or phrase]", "Moderation", "Admins configure which words or phrases the anti-swear filter watches."),
    ("!choose <option> | <option> ...", "Fun", "Let Nightfall pick one of up to 20 options."),
    ("!roll [NdM]", "Fun", "Roll a die, such as `!roll 20` or `!roll 3d8`."),
    ("!rps <rock|paper|scissors>", "Fun", "Play rock, paper, scissors against Nightfall."),
    ("!quote", "Fun", "Get a little Nightfall wisdom."),
    ("!reverse <text>", "Fun", "Reverse a short line of text."),
    ("!mock <text>", "Fun", "mOcK a short line of text."),
    ("!color <hex>", "Utility", "Preview a six-digit color, such as `!color 8B5CF6`."),
    ("!avatar [@member]", "Utility", "Show your avatar or another member's avatar."),
    ("!userinfo [@member]", "Utility", "Show account, server join, and role details."),
    ("!serverinfo", "Utility", "Show useful information about this server."),
    ("!aiimage <description>", "Creative AI", "Image generation is currently unavailable in the free AI setup. Alias: `!aiart`."),
    ("!ask <question>", "Creative AI", "Ask Nightfall AI a general question and get a concise answer."),
    ("!story <idea>", "Creative AI", "Create a short original story from your idea."),
    ("!roast [@member]", "Creative AI", "Give yourself or a member a gentle, playful roast."),
    ("!compliment [@member]", "Creative AI", "Generate a warm, upbeat compliment."),
    ("!riddle", "Creative AI", "Generate an original riddle and reveal its answer."),
    ("!poem [topic]", "Creative AI", "Write a short poem about a topic."),
    ("!joke [topic]", "Creative AI", "Generate a clean, short joke about a topic."),
    ("!caption <idea>", "Creative AI", "Create a short social caption and up to three hashtags."),
    ("!namegen <theme>", "Creative AI", "Generate 8 distinct names for a theme. Alias: !names."),
    ("!quiz <topic>", "Creative AI", "Create a multiple-choice trivia question with the correct answer and explanation."),
    ("!ticket", "Tickets", "Show ticket command usage."),
    ("!ticket panel", "Tickets", "Post the configured ticket panel."),
    ("!ticket questions <type> <questions>", "Tickets", "Set questions for a ticket type."),
    ("!appeal server", "Tickets", "Show or set the appeal server information."),
    ("!appeal_server", "Tickets", "Show appeal server information. Also accepts !appealserver."),
    ("!autoreaction #channel <emoji>", "Community", "Set automatic reactions for a channel."),
    ("!role give <member|everyone> @role", "Roles", "Give a role to a member or eligible members."),
    ("!role make <name> [#color]", "Roles", "Create a role with an optional hex color."),
    ("!reset invites <member|everyone>", "Invites", "Reset tracked invite counts."),
    ("!invites [@member]", "Invites", "Show invite counts for you or a member."),
    ("!invited [@member]", "Invites", "Show users invited by you or a member."),
    ("!inviter @member", "Invites", "Show who invited a member."),
    ("!j4j allowed", "Community", "Show the join-for-join allowlist."),
    ("!j4j dm <on|off>", "Community", "Toggle join-for-join direct messages."),
    ("!giveaway <duration> <winners> <prize>", "Giveaways", "Start a giveaway."),
    ("!giveaway reroll <message_id>", "Giveaways", "Choose a new winner for a giveaway."),
    ("!giveaway end <message_id>", "Giveaways", "End a giveaway early."),
    ("!stick <message>", "Utility", "Make a message sticky in the current channel."),
    ("!unstick", "Utility", "Remove the sticky message from the current channel."),
    ("!proof <action>", "Community", "Use the configured proof workflow. Staff only."),
    ("!daily", "Games", "Claim your daily coins."),
    ("!balance [@member]", "Games", "Show your coin balance or another member's."),
    ("!coinflip <bet> <heads|tails>", "Games", "Bet coins on a coin flip."),
    ("!highlow <bet>", "Games", "Play High-Low with a coin bet."),
    ("!blackjack <bet>", "Games", "Play Blackjack with a coin bet."),
    ("!roulette <bet> <pick>", "Games", "Play Roulette with a coin bet."),
    # Slash-command directory: keep every existing ! command above and also advertise the new / equivalents.
    ("/help", "Utility", "Show Nightfall's command help as a Discord slash command."),
    ("/about", "Utility", "Show Nightfall's launch information."),
    ("/setup", "Admin tools", "Open the interactive server setup dashboard."),
    ("/ban @member [reason]", "Moderation", "Ban a member. Staff only."),
    ("/kick @member [reason]", "Moderation", "Kick a member. Staff only."),
    ("/warn @member [reason]", "Moderation", "Warn a member. Staff only."),
    ("/purge <amount>", "Moderation", "Delete recent messages."),
    ("/warnings @member", "Moderation", "Show a member's warning record."),
    ("/clearwarnings @member", "Moderation", "Clear a member's warning record."),
    ("/timeout @member <duration> [reason]", "Moderation", "Temporarily timeout a member."),
    ("/lock", "Moderation", "Lock the current channel."),
    ("/unlock", "Moderation", "Unlock the current channel."),
    ("/slowmode <seconds>", "Moderation", "Set channel slowmode."),
    ("/jail @member [reason]", "Moderation", "Jail a member using the configured jail system."),
    ("/unjail @member [reason]", "Moderation", "Release a jailed member."),
    ("/announce #channel <message>", "Admin tools", "Post a server announcement."),
    ("/poll <question and options>", "Community", "Create a reaction poll."),
    ("/afk [reason]", "Utility", "Set your AFK status."),
    ("/8ball <question>", "Fun", "Ask the Nightfall 8-Ball a question."),
    ("/mommycount [@member]", "Fun", "Count tracked uses of mommy in this server."),
    ("/swearcount [@member]", "Moderation", "Show configured swear-word match counts."),
    ("/antiswear <on|off|status>", "Moderation", "Manage the configurable anti-swear filter."),
    ("/swearwords <add|remove|list> [word or phrase]", "Moderation", "Configure filtered words or phrases."),
    ("/choose <option> | <option> ...", "Fun", "Let Nightfall pick from up to 20 options."),
    ("/roll [NdM]", "Fun", "Roll dice."),
    ("/rps <rock|paper|scissors>", "Fun", "Play rock, paper, scissors."),
    ("/quote", "Fun", "Get a little Nightfall wisdom."),
    ("/reverse <text>", "Fun", "Reverse a short line of text."),
    ("/mock <text>", "Fun", "Mock a short line of text."),
    ("/color <hex>", "Utility", "Preview a six-digit color."),
    ("/avatar [@member]", "Utility", "Show an avatar."),
    ("/userinfo [@member]", "Utility", "Show account and server details."),
    ("/serverinfo", "Utility", "Show server information."),
    ("/ping", "Utility", "Show Nightfall latency and online status."),
    ("/membercount", "Utility", "Show total members, humans, and bots."),
    ("/roleinfo @role", "Roles", "Show useful information about a role."),
    ("/channelinfo [#channel]", "Utility", "Show useful information about a text channel."),
    ("/ask <question>", "Creative AI", "Ask Nightfall AI a general question."),
    ("/story <idea>", "Creative AI", "Create a short original story."),
    ("/roast [@member]", "Creative AI", "Give a gentle playful roast."),
    ("/compliment [@member]", "Creative AI", "Generate a warm compliment."),
    ("/riddle", "Creative AI", "Generate an original riddle."),
    ("/poem [topic]", "Creative AI", "Write a short poem."),
    ("/joke [topic]", "Creative AI", "Generate a clean short joke."),
    ("/caption <idea>", "Creative AI", "Create a short social caption."),
    ("/namegen <theme>", "Creative AI", "Generate names for a theme."),
    ("/quiz <topic>", "Creative AI", "Create a multiple-choice trivia question."),
    ("/aiimage <description>", "Creative AI", "Generate an image when the configured image service is available."),
    ("/ticket", "Tickets", "Show ticket command usage."),
    ("/ticket panel", "Tickets", "Post the configured ticket panel."),
    ("/ticket questions <type> <questions>", "Tickets", "Set questions for a ticket type."),
    ("/appeal server", "Tickets", "Show or set the appeal server information."),
    ("/appeal_server", "Tickets", "Show appeal server information."),
    ("/autoreaction #channel <emoji>", "Community", "Set automatic reactions for a channel."),
    ("/role give <member|everyone> @role", "Roles", "Give a role to a member or eligible members."),
    ("/role make <name> [#color]", "Roles", "Create a role with an optional hex color."),
    ("/reset invites <member|everyone>", "Invites", "Reset tracked invite counts."),
    ("/invites [@member]", "Invites", "Show invite counts."),
    ("/invited [@member]", "Invites", "Show users invited by a member."),
    ("/inviter @member", "Invites", "Show who invited a member."),
    ("/j4j allowed", "Community", "Toggle whether J4J entries are allowed."),
    ("/j4j dm <on|off>", "Community", "Toggle J4J welcome direct messages."),
    ("/giveaway <duration> <winners> <prize>", "Giveaways", "Start a giveaway."),
    ("/giveaway reroll <message_id>", "Giveaways", "Choose a new giveaway winner."),
    ("/giveaway end <message_id>", "Giveaways", "End a giveaway early."),
    ("/stick <message>", "Utility", "Make a message sticky."),
    ("/unstick", "Utility", "Remove the sticky message."),
    ("/proof <action>", "Community", "Use the configured proof workflow. Staff only."),
]


# Initialize persistent storage on both Gunicorn imports and direct starts.
try:
    init_db()
except psycopg.Error as exc:
    app.logger.error("Database initialization failed: %s", type(exc).__name__)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
