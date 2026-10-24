import os
from io import BytesIO
import json
import secrets
import base64
import hashlib
import threading
import time
from datetime import timedelta
from collections import defaultdict, deque
from hmac import compare_digest
from functools import wraps
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET

import requests
from PIL import Image
import psycopg
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = (os.getenv("SESSION_SECRET") or os.getenv("ROBLOX_OAUTH_CLIENT_SECRET") or "").strip() or secrets.token_urlsafe(48)
app.permanent_session_lifetime = timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
APP_STARTED_AT = time.time()
APP_REQUEST_COUNT = 0
APP_METRICS_LOCK = threading.Lock()
MEMORY_ANNOUNCEMENTS = []
MEMORY_ANNOUNCEMENT_ID = 1
MEMORY_CUSTOM_COMMANDS = []
MEMORY_CUSTOM_COMMAND_ID = 1
MEMORY_DEVELOPERS = [{"discord_id":"1418291387668893699","display_name":"Owner","role":"Owner"},{"discord_id":"1242411642252431385","display_name":"Owner","role":"Owner"},{"discord_id":"1275463389941858346","display_name":"Developer","role":"Developer"}]
DEVELOPER_PROFILE_CACHE = {}
DEVELOPER_PROFILE_CACHE_TTL = 21600
BROWSER_ACTIONS = defaultdict(deque)
BROWSER_ACTIONS_LOCK = threading.Lock()
PASSIVE_VERIFICATION_ENDPOINTS = {
    "create_support_ticket", "add_support_message", "support_ai", "suggestions",
    "social_submit_video", "social_follow", "social_report", "post_review",
    "claim_daily", "update_profile", "social_like", "social_comment",
    "mark_notifications_read", "api_award_xp",
}




@app.get("/google5b8141aa320c129f.html")
def google_search_console_verification():
    # Flask does not serve arbitrary files placed in the repository root.
    # Return Google's exact verification-file contents at the expected URL.
    return Response(
        "google-site-verification: google5b8141aa320c129f.html\n",
        mimetype="text/plain",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/gargand-lion.jpg")
def gargand_lion_asset():
    """Serve the GARGAND lion; prefer the compressed custom PFP if installed."""
    image_path = os.path.join(app.root_path, "static", "gargand-pfp.jpg.b64")
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = base64.b64decode(image_file.read().strip(), validate=True)
        return Response(
            image_bytes, mimetype="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
        )
    except (OSError, ValueError):
        # Existing checked-in lion mark keeps the site and embeds functional until the PFP is installed.
        fallback = os.path.join(app.root_path, "static", "gargand-mark.svg")
        try:
            with open(fallback, "rb") as logo_file:
                return Response(logo_file.read(), mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})
        except OSError:
            return "GARGAND image unavailable", 404


@app.get("/gargand-lion-4k.jpg")
def gargand_lion_4k_asset():
    """Keep the legacy image URL fast by serving the original 1024px source."""
    return gargand_lion_asset()

@app.get("/gargand-bar.gif")
def gargand_bar_asset():
    """Serve the small animated GARGAND gold divider used by Discord embeds."""
    image_path = os.path.join(app.root_path, "static", "gargand-gold-bar.gif.b64")
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = base64.b64decode(image_file.read().strip(), validate=True)
        return Response(
            image_bytes, mimetype="image/gif",
            headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
        )
    except (OSError, ValueError) as exc:
        app.logger.warning("GARGAND divider unavailable: %s", type(exc).__name__)
        return "GARGAND divider unavailable", 404


@app.after_request
def harden_oauth_callback_response(response):
    # OAuth callback URLs contain short-lived authorization codes and state.
    # Keep them out of caches, referrers, and search indexes.
    if request.path == "/oauth/callback":
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@app.before_request
def count_site_request():
    global APP_REQUEST_COUNT
    with APP_METRICS_LOCK:
        APP_REQUEST_COUNT += 1


@app.before_request
def verify_passive_browser_actions():
    """Quietly protect browser form/API writes without showing a CAPTCHA."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.endpoint not in PASSIVE_VERIFICATION_ENDPOINTS:
        return None

    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        return jsonify({"ok": False, "error": "Refresh the page and try again."}), 403
    origin = request.headers.get("Origin")
    if origin:
        parsed_origin = urlparse(origin)
        if parsed_origin.scheme not in {"http", "https"} or parsed_origin.netloc.lower() != request.host.lower():
            return jsonify({"ok": False, "error": "Refresh the page and try again."}), 403

    expected = str(session.get("browser_verification_token") or "")
    issued_at = session.get("browser_verification_issued_at", 0)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    supplied = (
        request.headers.get("X-Gargand-Browser-Check")
        or request.form.get("browser_check")
        or payload.get("browser_check")
    )
    honeypot = request.form.get("company_website") or payload.get("company_website")
    if str(honeypot or "").strip():
        return jsonify({"ok": False, "error": "The request could not be verified."}), 400
    try:
        issued_at = float(issued_at)
    except (TypeError, ValueError):
        issued_at = 0
    if (
        not expected
        or not supplied
        or not compare_digest(expected, str(supplied))
        or time.time() - issued_at > 86400
        or issued_at > time.time() + 60
    ):
        return jsonify({"ok": False, "error": "Refresh the page and try again."}), 403

    session_key = hashlib.sha256(expected.encode("utf-8")).hexdigest()[:24]
    bucket_key = (session_key, request.endpoint)
    now = time.monotonic()
    limit = 6 if request.endpoint == "support_ai" else 10
    with BROWSER_ACTIONS_LOCK:
        bucket = BROWSER_ACTIONS[bucket_key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return jsonify({"ok": False, "error": "Please wait a moment before trying again."}), 429
        bucket.append(now)
        if len(BROWSER_ACTIONS) > 5000:
            for stale_key in list(BROWSER_ACTIONS)[:1000]:
                BROWSER_ACTIONS.pop(stale_key, None)
    return None


@app.context_processor
def inject_admin_csrf_token():
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token

    browser_token = session.get("browser_verification_token")
    issued_at = session.get("browser_verification_issued_at", 0)
    try:
        token_expired = time.time() - float(issued_at) > 86400
    except (TypeError, ValueError):
        token_expired = True
    if not browser_token or token_expired:
        browser_token = secrets.token_urlsafe(32)
        session["browser_verification_token"] = browser_token
        session["browser_verification_issued_at"] = time.time()
    return {"csrf_token": token, "browser_verification_token": browser_token}


def valid_admin_csrf():
    expected = session.get("admin_csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(expected and supplied and compare_digest(expected, supplied))


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
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://gargand-bot.onrender.com/oauth/callback")
BOT_BRIDGE_SECRET = (os.getenv("GARGAND_BRIDGE_SECRET") or os.getenv("NIGHTFALL_BRIDGE_SECRET") or "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_LOGIN_FAILURES = {}
INVITE_URL = (os.getenv("INVITE_URL") or (f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&scope=bot%20applications.commands" if DISCORD_CLIENT_ID else "#")).strip()
SUPPORT_URL = "https://discord.gg/AG2m6u9Ahm"  # Official Gargand support invite; do not override with stale deployment env vars.
OFFICIAL_GUILD_ID = "1561076743236747387"
ADMIN_DISCORD_USER_ID = "1275463389941858346"
GARGAND_BOT_TOKEN = (os.getenv("GARGAND_BOT_TOKEN") or os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN") or "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
NIGHTFALL_YOUTUBE_CHANNEL_ID = (os.getenv("GARGAND_YOUTUBE_CHANNEL_ID") or os.getenv("NIGHTFALL_YOUTUBE_CHANNEL_ID") or "").strip()
ROBLOX_BRIDGE_SECRET = (os.getenv("ROBLOX_BRIDGE_SECRET") or BOT_BRIDGE_SECRET).strip()
ROBLOX_OAUTH_CLIENT_ID = os.getenv("ROBLOX_OAUTH_CLIENT_ID", "").strip()
ROBLOX_OAUTH_CLIENT_SECRET = os.getenv("ROBLOX_OAUTH_CLIENT_SECRET", "").strip()
ROBLOX_OAUTH_REDIRECT_URI = (os.getenv("ROBLOX_OAUTH_REDIRECT_URI") or "https://gargand-bot.onrender.com/roblox/oauth/callback").strip()
ROBLOX_OAUTH_AUTHORIZE_URL = "https://apis.roblox.com/oauth/v1/authorize"
ROBLOX_OAUTH_TOKEN_URL = "https://apis.roblox.com/oauth/v1/token"
ROBLOX_OAUTH_USERINFO_URL = "https://apis.roblox.com/oauth/v1/userinfo"

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8

# Only settings that the bot actually reads are editable from the dashboard.
CHANNEL_SETTINGS = {
    "logs_channel_id", "ticket_category_id", "ticket_panel_channel_id",
    "welcome_channel_id", "leave_channel_id", "verification_channel_id",
    "command_channel_id", "vouch_channel_id", "feedback_channel_id", "suggestions_channel_id",
    "proof_channel_id", "gamble_channel_id", "staff_application_channel_id",
    "jail_category_id", "jail_chat_channel_id", "jail_appeal_channel_id",
    "autoreaction_channel_id", "modlog_channel_id", "levelup_channel_id",
    "analytics_channel_id", "automod_log_channel_id", "giveaway_channel_id"
}
ROLE_SETTINGS = {"staff_role_id", "autorole_id", "booster_role_id", "jail_role_id", "verified_role_id", "unverified_role_id", "muted_role_id"}
TOGGLE_SETTINGS = {
    "anti_raid", "raid_auto_lockdown", "anti_nuke", "anti_nuke_auto_lockdown", "anti_nuke_auto_ban", "anti_link", "j4j", "j4j_dm", "jail_enabled",
    "automod_spam", "automod_flood", "automod_mentions", "automod_bad_words",
    "xp_enabled", "economy_enabled", "analytics_enabled", "ai_memory_enabled",
    "giveaway_require_role"
}
TEXT_SETTINGS = {"prefix", "autoreaction_emoji", "appeal_invite_url", "automod_punishment"}
EDITABLE_SETTINGS = CHANNEL_SETTINGS | ROLE_SETTINGS | TOGGLE_SETTINGS | TEXT_SETTINGS | {
    "appeal_server_id", "ticket_options", "ticket_questions", "automod_max_messages",
    "automod_window_seconds", "automod_mention_limit", "xp_per_message",
    "xp_cooldown_seconds", "daily_coins"
} | {
    "anti_nuke_trusted_role_ids", "anti_nuke_window_seconds",
    "anti_nuke_threshold_channel_delete", "anti_nuke_threshold_role_delete",
    "anti_nuke_threshold_channel_update", "anti_nuke_threshold_role_update",
}
ANTI_NUKE_NUMERIC_RANGES = {
    "anti_nuke_window_seconds": (5, 60),
    "anti_nuke_threshold_channel_delete": (2, 10),
    "anti_nuke_threshold_role_delete": (2, 10),
    "anti_nuke_threshold_channel_update": (2, 10),
    "anti_nuke_threshold_role_update": (2, 10),
}
AUTOMOD_NUMERIC_RANGES = {
    "automod_max_messages": (3, 20),
    "automod_window_seconds": (3, 60),
    "automod_mention_limit": (2, 20),
}
SETTING_GROUPS = [
    ("general", "General", "Identity, prefix and logging", [("prefix", "Command prefix", "text"), ("logs_channel_id", "Logs channel", "channel"), ("staff_role_id", "Staff role", "role")]),
    ("community", "Community", "Welcome, roles, feedback, applications and XP", [("welcome_channel_id", "Welcome channel", "channel"), ("leave_channel_id", "Leave channel", "channel"), ("autorole_id", "Auto role", "role"), ("vouch_channel_id", "Vouch channel", "channel"), ("feedback_channel_id", "Feedback channel", "channel"), ("suggestions_channel_id", "Suggestions channel", "channel"), ("proof_channel_id", "Proof channel", "channel"), ("booster_role_id", "Booster role", "role"), ("staff_application_channel_id", "Applications channel", "channel"), ("autoreaction_channel_id", "Auto reaction channel", "channel"), ("autoreaction_emoji", "Auto reaction emoji", "text"), ("xp_enabled", "XP & levels", "toggle"), ("levelup_channel_id", "Level-up channel", "channel"), ("xp_per_message", "XP per message", "number"), ("xp_cooldown_seconds", "XP cooldown (seconds)", "number")]),
    ("security", "Security & Auto-Mod", "Automatic protection and moderation", [("anti_raid", "Anti-raid protection", "toggle"), ("raid_auto_lockdown", "Auto-lock channels during a join surge", "toggle"), ("anti_nuke", "Anti-nuke protection", "toggle"), ("anti_nuke_trusted_role_ids", "Trusted anti-nuke roles", "roles"), ("anti_nuke_window_seconds", "Anti-nuke event window (seconds)", "number"), ("anti_nuke_threshold_channel_delete", "Channel deletions before alert", "number"), ("anti_nuke_threshold_role_delete", "Role deletions before alert", "number"), ("anti_nuke_threshold_channel_update", "Channel edits before alert", "number"), ("anti_nuke_threshold_role_update", "Role edits before alert", "number"), ("anti_nuke_auto_lockdown", "Temporarily lock channels at threshold", "toggle"), ("anti_nuke_auto_ban", "Ban actor at threshold", "toggle"), ("anti_link", "Block links", "toggle"), ("automod_spam", "Anti-spam", "toggle"), ("automod_flood", "Anti-flood", "toggle"), ("automod_mentions", "Mention protection", "toggle"), ("automod_bad_words", "Configured word filter", "toggle"), ("automod_punishment", "Auto-mod punishment", "choice"), ("automod_max_messages", "Max messages in window", "number"), ("automod_window_seconds", "Spam window (seconds)", "number"), ("automod_mention_limit", "Mention limit", "number"), ("automod_log_channel_id", "Auto-mod log channel", "channel"), ("j4j", "Join for join", "toggle"), ("j4j_dm", "J4J direct messages", "toggle"), ("verification_channel_id", "Verification channel", "channel"), ("command_channel_id", "Command-only channel", "channel")]),
    ("tickets", "Tickets & appeals", "Ticket panel, categories, questions and appeals", [("ticket_panel_channel_id", "Ticket panel channel", "channel"), ("ticket_category_id", "Ticket category", "channel"), ("ticket_options", "Ticket types (comma separated)", "list"), ("ticket_questions", "Ticket questions (JSON)", "json"), ("appeal_server_id", "Appeal server ID", "number"), ("appeal_invite_url", "Appeal invite URL", "text")]),
    ("moderation", "Moderation & jail", "Jail, giveaways and analytics", [("jail_role_id", "Jail role", "role"), ("jail_category_id", "Jail category", "channel"), ("jail_chat_channel_id", "Jail chat", "channel"), ("jail_appeal_channel_id", "Jail appeals", "channel"), ("giveaway_channel_id", "Giveaway channel", "channel"), ("giveaway_require_role", "Giveaways require role", "toggle"), ("analytics_enabled", "Server analytics", "toggle"), ("analytics_channel_id", "Analytics channel", "channel"), ("economy_enabled", "Community economy", "toggle"), ("daily_coins", "Daily coins", "number"), ("ai_memory_enabled", "AI channel memory", "toggle")]),
]


def discord_headers():
    return {"Authorization": f"Bearer {session['access_token']}"}


def is_admin():
    """Admin access requires a Discord OAuth session for the explicitly allowed user."""
    user = session.get("user") or {}
    return bool(session.get("admin") and str(user.get("id", "")) == ADMIN_DISCORD_USER_ID)


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
    public_get = {"/", "/commands", "/planets", "/guidelines", "/announcements", "/suggestions", "/support", "/terms", "/socials", "/security", "/verification", "/gargand-lion.jpg", "/gargand-lion-4k.jpg", "/gargand-bar.gif"}
    public_secret_api = set()
    public_bot_api = {"/api/bot/heartbeat", "/api/bot/pull", "/api/bot/announcements"}
    endpoint = request.endpoint or ""
    if endpoint in {"login", "oauth_callback", "health"} or endpoint.startswith("static") or endpoint.startswith("admin"):
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
    supplied = request.headers.get("X-Gargand-Bridge-Key", "")
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
    if not is_admin():
        return redirect(url_for("admin_login"))
    events = []
    summary = {"commands": 0, "messages": 0, "members_joined": 0, "members_left": 0, "tickets": 0, "closed_tickets": 0, "dashboard_actions": 0, "settings_updates": 0, "forms": 0, "security_incidents": 0}
    if DATABASE_URL:
        with db_connect() as conn:
            rows = conn.execute("SELECT event_type,guild_id,guild_name,user_id,username,command_name,metadata,created_at FROM bot_telemetry ORDER BY id DESC LIMIT 500").fetchall()
            events = []
            for r in rows:
                try:
                    metadata = json.loads(r[6]) if isinstance(r[6], str) else (r[6] or {})
                except (TypeError, ValueError):
                    metadata = {}
                if isinstance(metadata, dict) and "answers" in metadata:
                    metadata = dict(metadata)
                    metadata.pop("answers", None)
                    metadata["ticket_answers"] = "redacted"
                events.append({
                    "event_type": r[0], "guild_id": r[1], "guild_name": r[2],
                    "user_id": r[3], "username": r[4], "command_name": r[5],
                    "metadata": json.dumps(metadata, ensure_ascii=False),
                    "created_at": r[7],
                })
            for key, label in (
                ("command_used","commands"),
                ("message_seen","messages"),
                ("member_joined","members_joined"),
                ("member_left","members_left"),
                ("ticket_created","tickets"),
                ("ticket_closed","closed_tickets"),
                ("dashboard_action","dashboard_actions"),
                ("settings_updated","settings_updates"),
                ("form_submitted","forms"),
                ("security_incident","security_incidents"),
            ):
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
                "health": guild.get("health") if isinstance(guild.get("health"), dict) else {},
                # Preserve the bot-authorized channel/role lists; the dashboard
                # resource endpoint depends on these fields to populate selectors.
                "channels": guild.get("channels") if isinstance(guild.get("channels"), list) else [],
                "roles": guild.get("roles") if isinstance(guild.get("roles"), list) else [],
                "music": guild.get("music") if isinstance(guild.get("music"), dict) else {},
                "community": guild.get("community") if isinstance(guild.get("community"), dict) else {},
                "notifications": guild.get("notifications") if isinstance(guild.get("notifications"), dict) else {},
                "audit": guild.get("audit") if isinstance(guild.get("audit"), list) else [],
                "command_catalog": guild.get("command_catalog") if isinstance(guild.get("command_catalog"), list) else [],
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


def user_is_guild_admin(guild_id):
    try:
        response = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
        if response.status_code != 200:
            return False
        guild = next((item for item in response.json() if str(item.get("id")) == str(guild_id)), None)
        if not guild:
            return False
        permissions = int(guild.get("permissions", "0"))
        return (permissions & ADMINISTRATOR) == ADMINISTRATOR
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
            "SELECT discord_id, roblox_user_id, link_token, premium, premium_source, premium_expires_at, started_redeemed, updated_at FROM roblox_links WHERE discord_id=%s",
            (str(discord_id),),
        ).fetchone()
    if not row:
        return None
    return {
        "discord_id": row[0], "roblox_user_id": row[1], "link_token": row[2],
        "premium": bool(row[3]), "premium_source": row[4],
        "premium_expires_at": float(row[5] or 0), "started_redeemed": bool(row[6]), "updated_at": row[7],
    }

def roblox_premium_active(link):
    if not link:
        return False
    expires_at = float(link.get("premium_expires_at") or 0)
    if link.get("premium_source") == "started":
        return expires_at > time.time()
    if link.get("premium"):
        return True
    return expires_at > time.time()

ROBLOX_PREMIUM_PASS_URL = "https://www.roblox.com/game-pass/1747241092"
ROBLOX_ARCADE_OFFER_URL = "https://www.roblox.com/game-pass/1744202935"
STARTED_CODE = "started"
PREMIUM_FULL_PRICE = 179
PREMIUM_ARCADE_PRICE = 70



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
    # Only publish bot repository releases; website commits stay internal.
    repos = [
        ("bot", "Bot Update", "popescuulucaap-source/discord-bot"),
    ]
    try:
        with db_connect() as conn:
            for repo_kind, label, repo_name in repos:
                response = requests.get(
                    f"https://api.github.com/repos/{repo_name}/commits",
                    params={"per_page": 1},
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "Gargand-Updates"},
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
                announcement_title = f"{label} • {message[:120]}"
                announcement_body = f"Automatically detected from GitHub commit {sha[:7]}. {message}"
                announcement_kind = "bot" if repo_kind == "bot" else "website"
                conn.execute(
                    "INSERT INTO announcements (title, body, date, kind) VALUES (%s,%s,%s,%s)",
                    (announcement_title, announcement_body, __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d"), announcement_kind),
                )
                conn.execute(
                    "INSERT INTO bot_jobs (guild_id, kind, payload) VALUES (%s,%s,%s)",
                    (OFFICIAL_GUILD_ID, "official_announcement", json.dumps({"title": announcement_title, "body": announcement_body, "kind": announcement_kind, "url": "https://gargand-bot.onrender.com/announcements"})),
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
            cur.execute("CREATE TABLE IF NOT EXISTS developers (discord_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Developer', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            for developer_id, display_name, role in [("1418291387668893699", "Owner", "Owner"), ("1242411642252431385", "Owner", "Owner"), ("1275463389941858346", "Developer", "Developer")]:
                cur.execute("INSERT INTO developers (discord_id, display_name, role) VALUES (%s,%s,%s) ON CONFLICT (discord_id) DO NOTHING", (developer_id, display_name, role))
            cur.execute("CREATE TABLE IF NOT EXISTS repository_updates (repo_kind TEXT PRIMARY KEY, commit_sha TEXT NOT NULL, checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("ALTER TABLE announcements ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'website'")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_telemetry (id BIGSERIAL PRIMARY KEY, event_type TEXT NOT NULL, guild_id TEXT, guild_name TEXT, user_id TEXT, username TEXT, command_name TEXT, metadata TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE INDEX IF NOT EXISTS bot_telemetry_created_at_idx ON bot_telemetry(created_at DESC)")
            cur.execute("CREATE TABLE IF NOT EXISTS security_incident_reviews (guild_id TEXT NOT NULL, case_id TEXT NOT NULL, reviewed_by TEXT NOT NULL, reviewer_name TEXT NOT NULL, reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), note TEXT NOT NULL DEFAULT '', PRIMARY KEY (guild_id, case_id))")
            # Seed the public bot release announcements once, without duplicating them.
            bot_releases = [
                (
                    "Gargand v1.0 • Bot Update",
                    "Gargand v1.0 introduced the core Discord bot experience, moderation tools and server-management features.",
                    "2026-10-01",
                ),
                (
                    "Gargand v1.1 • Bot Update",
                    "Gargand v1.1 expanded the bot with additional server tools, protection features and quality-of-life improvements.",
                    "2026-10-03",
                ),
                (
                    "Gargand v1.2 • Bot Update",
                    "Gargand v1.2 brought new bot improvements, expanded command support and stronger server-management features.",
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
            # Publish the recent merged website and bot releases in the public Updates feed.
            release_announcements = [
                (
                    "Verification hardening • Bot Update",
                    "Member verification now uses a private four-word, three-digit challenge tied to the correct server and pending role. Cooldowns and temporary retry limits make repeated guessing harder, longer risk-based phrases stay readable, and the bot keeps the unverified role in place until verification succeeds.",
                    "2026-10-20",
                    "bot",
                ),
                (
                    "Moderation cases, appeals & raid response • Bot Update",
                    "Staff can track searchable moderation and security cases, while members can submit private appeals for eligible warning or timeout cases. Staged raid protection can apply a timed posting lockdown and restore saved channel permissions; join-risk signals inform verification without automatically banning new members.",
                    "2026-10-20",
                    "bot",
                ),
                (
                    "Cleaner embeds & setup health • Bot Update",
                    "Standard bot embeds no longer use the animated GIF divider. The bot also reports required permissions, configured channel access, and role hierarchy to the website setup health panel, helping admins catch configuration problems earlier.",
                    "2026-10-20",
                    "bot",
                ),
                (
                    "Staged anti-nuke alerts & recovery • Bot Update",
                    "Anti-nuke protection now watches channel and role deletions or monitored edits, checks Discord audit-log actors, and supports trusted roles and per-action thresholds. Optional temporary lockdown and automatic bans are off by default; administrators can inspect status with !antinuke and restore saved channel/role settings with !recover <case id>.",
                    "2026-10-20",
                    "bot",
                ),
            ]
            for title, body, date, kind in release_announcements:
                cur.execute("SELECT 1 FROM announcements WHERE title=%s LIMIT 1", (title,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO announcements (title, body, date, kind) VALUES (%s,%s,%s,%s)",
                        (title, body, date, kind),
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
            cur.execute("CREATE TABLE IF NOT EXISTS premium_guilds (guild_id TEXT PRIMARY KEY, discord_id TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'purchase', expires_at DOUBLE PRECISION NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("ALTER TABLE roblox_links ADD COLUMN IF NOT EXISTS started_redeemed BOOLEAN NOT NULL DEFAULT FALSE")
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
            cur.execute("ALTER TABLE arcade_rewards ALTER COLUMN code SET NOT NULL")
            cur.execute("CREATE TABLE IF NOT EXISTS site_settings (discord_id TEXT PRIMARY KEY, bio TEXT NOT NULL DEFAULT '', theme TEXT NOT NULL DEFAULT 'default', title TEXT NOT NULL DEFAULT '')")
            cur.execute("CREATE TABLE IF NOT EXISTS site_achievements (discord_id TEXT NOT NULL, achievement TEXT NOT NULL, unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (discord_id, achievement))")
            cur.execute("CREATE TABLE IF NOT EXISTS site_reputation (discord_id TEXT PRIMARY KEY, score INTEGER NOT NULL DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS social_likes (video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (video_id, discord_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS social_comments (id BIGSERIAL PRIMARY KEY, video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, username TEXT NOT NULL, avatar_url TEXT NOT NULL DEFAULT '', body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'approved', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        conn.commit()

def load_announcements():
    # Poll only the bot repository; website changes are not public updates.
    sync_repository_updates()
    if not DATABASE_URL:
        return [item for item in MEMORY_ANNOUNCEMENTS if item.get("kind") == "bot"]
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body, date, kind FROM announcements WHERE kind='bot' ORDER BY id DESC")
            return [{"id":r[0],"title":r[1],"body":r[2],"date":r[3],"kind":"bot"} for r in cur.fetchall()]

def save_announcement(title, body, kind="bot"):
    global MEMORY_ANNOUNCEMENT_ID
    kind = "bot"
    date=__import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    if not DATABASE_URL:
        MEMORY_ANNOUNCEMENTS.insert(0, {"id": MEMORY_ANNOUNCEMENT_ID, "title": title, "body": body, "date": date, "kind": kind})
        MEMORY_ANNOUNCEMENT_ID += 1
    else:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO announcements (title, body, date, kind) VALUES (%s, %s, %s, %s)",(title,body,date,kind))
            conn.commit()
    queue_bot_job(OFFICIAL_GUILD_ID, "official_announcement", {"title": title[:180], "body": body[:3500], "kind": kind, "url": "https://gargand-bot.onrender.com/announcements"})
def delete_announcement(announcement_id):
    if not DATABASE_URL:
        MEMORY_ANNOUNCEMENTS[:] = [item for item in MEMORY_ANNOUNCEMENTS if int(item.get("id", 0)) != int(announcement_id)]
        return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("DELETE FROM announcements WHERE id = %s",(announcement_id,))
        conn.commit()

def load_custom_commands():
    if not DATABASE_URL: return list(MEMORY_CUSTOM_COMMANDS)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, command, category, description FROM custom_commands ORDER BY id DESC")
            return [{"id":r[0],"command":r[1],"category":r[2],"description":r[3]} for r in cur.fetchall()]

def save_custom_command(command, category, description):
    global MEMORY_CUSTOM_COMMAND_ID
    if not DATABASE_URL:
        MEMORY_CUSTOM_COMMANDS.insert(0, {"id": MEMORY_CUSTOM_COMMAND_ID, "command": command, "category": category, "description": description})
        MEMORY_CUSTOM_COMMAND_ID += 1
        return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("INSERT INTO custom_commands (command, category, description) VALUES (%s, %s, %s)",(command,category,description))
        conn.commit()

def delete_custom_command(command_id):
    if not DATABASE_URL:
        MEMORY_CUSTOM_COMMANDS[:] = [item for item in MEMORY_CUSTOM_COMMANDS if int(item.get("id", 0)) != int(command_id)]
        return
    with db_connect() as conn:
        with conn.cursor() as cur: cur.execute("DELETE FROM custom_commands WHERE id = %s",(command_id,))
        conn.commit()

def public_discord_display_name(discord_id):
    """Resolve only a public Discord name for legacy placeholder developer labels."""
    discord_id = str(discord_id or "")
    if not discord_id.isdigit() or not GARGAND_BOT_TOKEN:
        return ""
    now = time.time()
    cached = DEVELOPER_PROFILE_CACHE.get(discord_id)
    if cached and cached[0] > now:
        return cached[1]
    display_name = ""
    try:
        response = requests.get(
            f"{DISCORD_API}/users/{discord_id}",
            headers={"Authorization": f"Bot {GARGAND_BOT_TOKEN}"},
            timeout=3,
        )
        if response.status_code == 200:
            user = response.json()
            display_name = str(user.get("global_name") or user.get("username") or "").strip()[:80]
    except (requests.RequestException, ValueError, TypeError):
        display_name = ""
    # Cache both successes and failures to avoid repeated API calls during page renders.
    DEVELOPER_PROFILE_CACHE[discord_id] = (
        now + (DEVELOPER_PROFILE_CACHE_TTL if display_name else 300),
        display_name,
    )
    if len(DEVELOPER_PROFILE_CACHE) > 500:
        for stale_id, entry in list(DEVELOPER_PROFILE_CACHE.items()):
            if entry[0] <= now:
                DEVELOPER_PROFILE_CACHE.pop(stale_id, None)
    return display_name


def present_developers(developers):
    """Replace generic role-as-name placeholders with public Discord display names."""
    result = []
    for developer in developers:
        item = dict(developer)
        name = str(item.get("display_name") or "").strip()
        role = str(item.get("role") or "").strip()
        if name and name.casefold() in {"owner", "developer", "contributor", "designer", "moderator"}:
            resolved = public_discord_display_name(item.get("discord_id"))
            if resolved:
                item["display_name"] = resolved
        result.append(item)
    return result


def load_developers():
    if not DATABASE_URL:
        rows = [dict(item) for item in MEMORY_DEVELOPERS]
    else:
        with db_connect() as conn:
            rows = conn.execute("SELECT discord_id, display_name, role FROM developers ORDER BY CASE WHEN LOWER(role)='owner' THEN 0 ELSE 1 END, display_name ASC").fetchall()
        rows = [{"discord_id": str(row[0]), "display_name": row[1], "role": row[2]} for row in rows]
    return present_developers(rows)


@app.context_processor
def inject_developers():
    try:
        return {"developers": load_developers()}
    except psycopg.Error as exc:
        app.logger.warning("Could not load developer list: %s", type(exc).__name__)
        return {"developers": present_developers(MEMORY_DEVELOPERS)}

def save_developer(discord_id, display_name, role):
    if not DATABASE_URL:
        for item in MEMORY_DEVELOPERS:
            if item["discord_id"] == discord_id:
                item.update(display_name=display_name, role=role)
                return
        MEMORY_DEVELOPERS.append({"discord_id": discord_id, "display_name": display_name, "role": role})
        return
    with db_connect() as conn:
        conn.execute("INSERT INTO developers (discord_id, display_name, role) VALUES (%s,%s,%s) ON CONFLICT (discord_id) DO UPDATE SET display_name=EXCLUDED.display_name, role=EXCLUDED.role", (discord_id, display_name, role))
        conn.commit()

def delete_developer(discord_id):
    if not DATABASE_URL:
        MEMORY_DEVELOPERS[:] = [item for item in MEMORY_DEVELOPERS if item["discord_id"] != discord_id]
        return
    with db_connect() as conn:
        conn.execute("DELETE FROM developers WHERE discord_id=%s", (discord_id,))
        conn.commit()

def all_commands():
    """Prefer the bot's live registry; fall back to the checked-in public catalog while it is offline."""
    raw_commands = None
    for guild_snapshot in bot_guild_snapshot():
        candidate = guild_snapshot.get("command_catalog")
        if isinstance(candidate, list) and candidate:
            raw_commands = candidate
            break
    if raw_commands is None:
        raw_commands = COMMANDS

    rows = []
    seen = set()
    for item in raw_commands:
        if isinstance(item, dict):
            command = str(item.get("command") or "").strip()
            category = str(item.get("category") or "Utility").strip() or "Utility"
            description = str(item.get("description") or "").strip()[:500]
            aliases = item.get("aliases") if isinstance(item.get("aliases"), list) else []
            permission = str(item.get("permission") or "Server members")[:100]
            mode = str(item.get("mode") or ("slash" if command.startswith("/") else "prefix")).lower()
            usage = str(item.get("usage") or command).strip()
            example = str(item.get("example") or usage).strip()
            name = str(item.get("name") or command).strip()
        else:
            try:
                command, category, description = item[:3]
            except (TypeError, ValueError):
                continue
            command = str(command).strip()
            category = str(category or "Utility").strip()
            description = str(description or "").strip()[:500]
            aliases = []
            permission = "Server members"
            mode = "slash" if command.startswith("/") else ("custom" if not command.startswith("!") else "prefix")
            usage = command
            example = command
            name = command
        if not command:
            continue
        unique_key = (command.casefold(), mode)
        if unique_key in seen:
            continue
        seen.add(unique_key)
        rows.append({
            "command": command,
            "name": name,
            "category": category,
            "description": description,
            "aliases": [str(alias)[:80] for alias in aliases[:20] if str(alias).strip()],
            "permission": permission,
            "mode": mode,
            "usage": usage,
            "example": example,
        })
    return rows

init_db()
sync_repository_updates(force=True)

@app.get("/")
def index():
    features = [
        ("🛡️","Moderation","Ban, kick, warn, timeout, lock, slowmode and jail."),
        ("🔐","Security","Anti-raid, anti-nuke, anti-link and verification."),
        ("🎫","Tickets","Interactive panels, questions, claims, proof and appeals."),
        ("👋","Server Tools","Welcome, leave, invites, vouches, feedback and boosters."),
        ("⚙️","Dashboard","Manage Gargand settings, security, tickets and server tools from the web."),
        ("🎁","Giveaways","Prize embeds, timers, winners, rerolls and early endings."),
        ("🎨","AI studio","Ask questions, create stories, jokes, poems, riddles, captions, names and quizzes with Gargand AI."),
    ]
    return render_template("index.html", features=features, command_count=len(all_commands()), developers=load_developers())

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    # A password alone is never sufficient; Discord OAuth must verify the exact allowlisted ID.
    user = session.get("user") or {}
    if is_admin():
        return redirect(url_for("admin"))
    if str(user.get("id", "")) == ADMIN_DISCORD_USER_ID:
        session["admin"] = True
        session["admin_authenticated_at"] = time.time()
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("admin"))
    if session.get("access_token"):
        return "Access denied. The admin panel is restricted to the verified Gargand developer account.", 403
    return redirect(url_for("login", next="/admin/panel"))

@app.get("/admin/panel")
def admin():
    if not is_admin():
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
    return render_template("admin.html", announcements=announcements, custom_commands=custom_commands, developers=load_developers(), database_enabled=bool(DATABASE_URL), stats=stats, bot_guilds=guilds)

@app.post("/admin/developer")
def admin_developer():
    if not is_admin():
        return redirect(url_for("admin_login"))
    if not valid_admin_csrf():
        return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    discord_id = (request.form.get("discord_id") or "").strip()
    display_name = (request.form.get("display_name") or "").strip()
    role = (request.form.get("role") or "Developer").strip()
    if not discord_id.isdigit() or not (17 <= len(discord_id) <= 20):
        return redirect(url_for("admin") + "?developer_error=invalid_id")
    if not display_name or len(display_name) > 80 or role not in {"Owner", "Developer", "Contributor", "Designer", "Moderator"}:
        return redirect(url_for("admin") + "?developer_error=invalid_details")
    save_developer(discord_id, display_name, role)
    return redirect(url_for("admin") + "#developers-admin")

@app.post("/admin/developer/<discord_id>/delete")
def admin_developer_delete(discord_id):
    if not is_admin():
        return redirect(url_for("admin_login"))
    if not valid_admin_csrf():
        return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    if discord_id.isdigit() and 17 <= len(discord_id) <= 20:
        delete_developer(discord_id)
    return redirect(url_for("admin") + "#developers-admin")

@app.post("/admin/command")
def admin_command():
    if not is_admin():
        return redirect(url_for("admin_login"))
    if not valid_admin_csrf():
        return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    cmd=(request.form.get("command") or "").strip()
    cat=(request.form.get("category") or "Other").strip()
    desc=(request.form.get("description") or "").strip()
    if cmd and desc:
        save_custom_command(cmd,cat,desc)
    return redirect(url_for("admin"))

@app.post("/admin/announcement")
def admin_announcement():
    if not is_admin():
        return redirect(url_for("admin_login"))
    if not valid_admin_csrf():
        return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    title=(request.form.get("title") or "Update").strip()
    body=(request.form.get("body") or "").strip()
    if title and body: save_announcement(title,body,"bot")
    return redirect(url_for("admin"))

@app.post("/admin/announcement/<int:announcement_id>/delete")
def admin_delete_announcement(announcement_id):
    if not is_admin(): return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    delete_announcement(announcement_id)
    return redirect(url_for("admin"))

@app.post("/admin/command/<int:command_id>/delete")
def admin_delete_command(command_id):
    if not is_admin(): return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return jsonify({"ok": False, "error": "Invalid session token. Refresh the admin page."}), 400
    delete_custom_command(command_id)
    return redirect(url_for("admin"))

@app.get("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))





@app.route("/support")
def support():
    return render_template("support.html")


@app.get("/terms")
def terms():
    return render_template("terms.html")


@app.get("/security")
def security():
    return render_template("security.html")


@app.get("/verification")
def verification():
    return render_template("verification.html")


@app.get("/socials")
def socials():
    return render_template("socials.html")

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
    subject = str(payload.get("subject") or "Gargand support").strip()[:120] or "Gargand support"
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
    if not is_admin(): return redirect(url_for("admin_login"))
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
    if not is_admin(): return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return "Invalid session token. Refresh the admin page.", 400
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
    """Read the public Gargand YouTube upload feed."""
    channel_id = NIGHTFALL_YOUTUBE_CHANNEL_ID
    if not channel_id:
        match = re.search(r"youtube\.com/channel/(UC[\w-]+)", "https://www.youtube.com/@nightfall-bot")
        channel_id = match.group(1) if match else ""
    if not channel_id:
        return []
    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
    try:
        response = requests.get(feed_url, timeout=10, headers={"User-Agent": "Gargand Community"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        ns = {"yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
        videos = []
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry")[:limit]:
            video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title", default="Gargand upload") or "Gargand upload").strip()
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
                "username": "Gargand • YouTube",
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
        app.logger.warning("Could not load Gargand YouTube feed: %s", type(exc).__name__)
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
    return jsonify({"ok": True, "message": "Report sent to Gargand moderators."})


@app.get("/admin/community")
def admin_community():
    if not is_admin():
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
    if not is_admin():
        return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return "Invalid session token. Refresh the admin page.", 400
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
    if not is_admin(): return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return "Invalid session token. Refresh the admin page.", 400
    with db_connect() as conn:
        conn.execute("UPDATE social_reports SET status='resolved' WHERE id=%s",(report_id,))
        conn.commit()
    return redirect(url_for("admin_community"))

@app.post("/admin/support/<int:ticket_id>/close")
def admin_support_close(ticket_id):
    if not is_admin(): return redirect(url_for("admin_login"))
    if not valid_admin_csrf(): return "Invalid session token. Refresh the admin page.", 400
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
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","HTTP-Referer":request.host_url,"X-Title":"Gargand Support"},json={"model":model,"messages":[{"role":"system","content":"You are Gargand's website support assistant. Answer the user's actual question instead of giving a generic fallback. Help with Gargand Discord commands, setup, moderation, tickets, website features, and troubleshooting. Be concise and honest. Never request passwords, tokens, API keys, or private credentials. If the issue requires admin access, explain that the user can open a human support ticket on the same Support page."},{"role":"user","content":message}]},timeout=20)
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
    if not is_admin():
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



@app.post("/api/bot/announcements")
def bot_publish_announcement():
    denied = require_bot_key()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()[:180]
    body = str(data.get("body") or "").strip()[:3500]
    kind = str(data.get("kind") or "bot").strip().lower()
    if not title or not body or kind not in {"bot", "website"}:
        return jsonify({"ok": False, "error": "title, body, and a valid kind are required"}), 400
    save_announcement(title, body, kind)
    return jsonify({"ok": True})

@app.get("/api/bot/status")
def bot_status():
    last_seen = None
    guild_count = len(bot_guild_snapshot())
    if DATABASE_URL:
        try:
            with db_connect() as conn:
                row = conn.execute(
                    "SELECT last_seen FROM bot_bridge_state WHERE state_id = 1"
                ).fetchone()
            if row and row[0]:
                last_seen = float(row[0])
        except psycopg.Error as exc:
            app.logger.warning("Could not read bot status heartbeat: %s", type(exc).__name__)
    if last_seen is None:
        with BOT_LOCK:
            last_seen = float(BOT_LAST_SEEN) if BOT_LAST_SEEN else None
            guild_count = len(BOT_GUILDS)
    age = max(0, int(time.time() - last_seen)) if last_seen else None
    online = bool(age is not None and age < 75)
    return jsonify({
        "ok": True,
        "online": online,
        "last_seen_age_seconds": age,
        "guild_count": guild_count,
    })

@app.get("/commands")
def commands():
    listed = all_commands()
    for item in load_custom_commands():
        command = str(item.get("command") or "").strip()
        if not command:
            continue
        listed.append({
            "command": command,
            "name": command,
            "category": str(item.get("category") or "Custom").strip()[:80],
            "description": str(item.get("description") or "").strip()[:500],
            "aliases": [],
            "permission": "Custom website entry",
            "mode": "custom",
            "usage": command,
            "example": command,
        })
    return render_template("commands.html", commands=listed)


@app.get("/guidelines")
def guidelines():
    return render_template("guidelines.html")


@app.get("/announcements")
def announcements():
    items = load_announcements()
    return render_template(
        "announcements.html",
        bot_updates=[item for item in items if item.get("kind") == "bot"],
    )


@app.get("/login")
def login():
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET or not DISCORD_REDIRECT_URI:
        return "Discord login is temporarily unavailable. Please contact Gargand support.", 503

    requested_next = request.args.get("next", "")
    # Only accept local paths, never external redirects after OAuth.
    if requested_next.startswith("/") and not requested_next.startswith("//"):
        session["oauth_next"] = requested_next

    # Start on Discord's official authorization endpoint; Gargand never collects Discord passwords.
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "consent",
    }
    return redirect(f"https://discord.com/oauth2/authorize?{urlencode(params)}")


@app.get("/oauth/callback")
def oauth_callback():
    # RFC 9207 issuer identification: reject authorization responses from any
    # issuer other than Discord before sending the authorization code anywhere.
    received_issuer = str(request.args.get("iss", "") or "")
    if received_issuer != "https://discord.com":
        session.pop("oauth_state", None)
        session.pop("oauth_next", None)
        return "Discord login could not be verified. Please restart from Gargand.", 400

    expected_state = str(session.pop("oauth_state", "") or "")
    received_state = str(request.args.get("state", "") or "")
    if not expected_state or not received_state or not compare_digest(expected_state, received_state):
        session.pop("oauth_next", None)
        return "Discord login could not be verified. Please restart from Gargand.", 400

    if request.args.get("error"):
        session.pop("oauth_next", None)
        return redirect(url_for("index"))

    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    try:
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
    except requests.RequestException as exc:
        app.logger.warning("Discord OAuth token request failed: %s", type(exc).__name__)
        return "Discord login is temporarily unavailable. Please try again.", 503

    if token.status_code != 200:
        app.logger.warning("Discord OAuth token exchange failed with HTTP %s", token.status_code)
        return "Discord login could not be completed. Please restart login from Gargand.", 400

    try:
        token_data = token.json()
        access_token = token_data["access_token"]
    except (ValueError, KeyError, TypeError):
        return "Discord login could not be completed. Please restart login from Gargand.", 400

    session["access_token"] = access_token
    session["refresh_token"] = token_data.get("refresh_token", "")
    session["token_expires_at"] = time.time() + int(token_data.get("expires_in", 604800))
    session.permanent = True
    session.modified = True
    award_site_xp("login", 25)

    try:
        me = requests.get(f"{DISCORD_API}/users/@me", headers=discord_headers(), timeout=12)
    except requests.RequestException as exc:
        app.logger.warning("Discord profile request failed: %s", type(exc).__name__)
        session.clear()
        return "Discord login is temporarily unavailable. Please try again.", 503
    if me.status_code != 200:
        session.clear()
        return "Could not verify your Discord profile. Please restart login.", 400

    user = me.json()
    session["user"] = user

    # Sync the verified developer account's current username to the public Developers card.
    if str(user.get("id", "")) == ADMIN_DISCORD_USER_ID:
        discord_username = str(user.get("username") or user.get("global_name") or "Developer")[:80]
        try:
            save_developer(ADMIN_DISCORD_USER_ID, discord_username, "Developer")
        except Exception as exc:
            app.logger.warning("Could not sync developer profile: %s", type(exc).__name__)

    next_path = session.pop("oauth_next", "")
    if next_path == "/admin/panel":
        if str(user.get("id", "")) != ADMIN_DISCORD_USER_ID:
            return "Access denied. The admin panel is restricted to the verified Gargand developer account.", 403
        session["admin"] = True
        session["admin_authenticated_at"] = time.time()
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("admin"))
    return redirect(next_path if next_path.startswith("/") and not next_path.startswith("//") else url_for("servers"))


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

    bot_api_error = None if bot_online() else "Gargand has not checked in with the website yet. Make sure the bot and bridge secret are configured."

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
    bot_error = None if bot_online() and bot_guild else "Gargand is offline or is not connected to this server."

    # Compact live server metrics for the control center.
    enabled_security = sum(bool(settings.get(key)) for key in ("anti_raid", "anti_nuke", "anti_link"))
    enabled_community = sum(bool(settings.get(key)) for key in ("welcome_channel_id", "leave_channel_id", "autorole_id", "booster_role_id", "vouch_channel_id", "feedback_channel_id", "suggestions_channel_id"))
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
        bot_health=bot_guild.get("health", {}) if bot_guild else {},
        bot_error=bot_error,
        setting_groups=SETTING_GROUPS,
        dashboard_stats=dashboard_stats,
    )


@app.get("/dashboard/<guild_id>/analytics")
@login_required
def guild_analytics(guild_id):
    if not user_can_manage_guild(guild_id):
        return "You do not have permission to manage this server.", 403

    period_days = 30 if request.args.get("days") == "30" else 7
    period = f"{period_days} days"
    bot_guild = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {})
    guild = {"id": str(guild_id), "name": bot_guild.get("name") or "Discord server"}
    summary = {"commands": 0, "tickets": 0, "active_members": 0, "moderation_cases": 0}
    daily_activity = []
    top_commands = []
    analytics_error = None

    if not DATABASE_URL:
        analytics_error = "Activity history needs shared database storage (DATABASE_URL)."
    else:
        try:
            with db_connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FILTER (WHERE event_type = 'command_used'), "
                    "COUNT(*) FILTER (WHERE event_type = 'ticket_created'), "
                    "COUNT(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL AND user_id <> '' AND event_type IN ('command_used', 'ticket_created')), "
                    "COUNT(*) FILTER (WHERE event_type = 'moderation_case') "
                    "FROM bot_telemetry WHERE guild_id = %s AND created_at >= NOW() - %s::interval",
                    (str(guild_id), period),
                ).fetchone()
                summary = {
                    "commands": int(row[0] or 0),
                    "tickets": int(row[1] or 0),
                    "active_members": int(row[2] or 0),
                    "moderation_cases": int(row[3] or 0),
                }
                rows = conn.execute(
                    "SELECT created_at::date AS activity_date, COUNT(*) AS total, "
                    "COUNT(*) FILTER (WHERE event_type = 'command_used') AS commands, "
                    "COUNT(*) FILTER (WHERE event_type = 'ticket_created') AS tickets, "
                    "COUNT(*) FILTER (WHERE event_type = 'moderation_case') AS moderation_cases "
                    "FROM bot_telemetry WHERE guild_id = %s AND created_at >= NOW() - %s::interval "
                    "GROUP BY created_at::date ORDER BY activity_date",
                    (str(guild_id), period),
                ).fetchall()
                daily_activity = [
                    {
                        "date": item[0],
                        "label": item[0].strftime("%b %d"),
                        "total": int(item[1] or 0),
                        "commands": int(item[2] or 0),
                        "tickets": int(item[3] or 0),
                        "moderation_cases": int(item[4] or 0),
                    }
                    for item in rows
                ]
                command_rows = conn.execute(
                    "SELECT command_name, COUNT(*) AS total FROM bot_telemetry "
                    "WHERE guild_id = %s AND event_type = 'command_used' "
                    "AND created_at >= NOW() - %s::interval AND command_name <> '' "
                    "GROUP BY command_name ORDER BY total DESC, command_name ASC LIMIT 5",
                    (str(guild_id), period),
                ).fetchall()
                top_commands = [{"name": str(item[0]), "total": int(item[1])} for item in command_rows]
        except psycopg.Error as exc:
            app.logger.warning("Could not load guild analytics: %s", type(exc).__name__)
            analytics_error = "Activity history is temporarily unavailable."

    max_daily_total = max((item["total"] for item in daily_activity), default=0)
    for item in daily_activity:
        item["bar_width"] = max(3, round(item["total"] * 100 / max_daily_total)) if max_daily_total else 0

    return render_template(
        "guild_analytics.html",
        guild=guild,
        period_days=period_days,
        summary=summary,
        daily_activity=daily_activity,
        top_commands=top_commands,
        analytics_error=analytics_error,
    )



@app.get("/dashboard/<guild_id>/moderation")
@login_required
def guild_moderation(guild_id):
    if not user_can_manage_guild(guild_id):
        return "You do not have permission to manage this server.", 403
    can_review_incidents = user_is_guild_admin(guild_id)

    bot_guild = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {})
    guild = {"id": str(guild_id), "name": bot_guild.get("name") or "Discord server"}
    cases = []
    moderation_error = None

    if not DATABASE_URL:
        moderation_error = "Moderation history needs shared database storage (DATABASE_URL)."
    else:
        try:
            with db_connect() as conn:
                rows = conn.execute(
                    "SELECT id, created_at, username, user_id, command_name, metadata, event_type "
                    "FROM bot_telemetry WHERE guild_id = %s AND event_type IN ('moderation_case','security_incident') "
                    "ORDER BY created_at DESC, id DESC LIMIT 100",
                    (str(guild_id),),
                ).fetchall()
                review_rows = conn.execute(
                    "SELECT case_id,reviewed_by,reviewer_name,reviewed_at FROM security_incident_reviews WHERE guild_id=%s",
                    (str(guild_id),),
                ).fetchall()
            for row in rows:
                try:
                    metadata = json.loads(row[5] or "{}")
                except (TypeError, ValueError):
                    metadata = {}
                if not isinstance(metadata, dict):
                    metadata = {}
                cases.append({
                    "id": int(row[0]),
                    "case_id": str(metadata.get("case_id") or row[0]),
                    "created_at": row[1],
                    "actor": str(row[2] or "Unknown staff member"),
                    "actor_id": str(row[3] or ""),
                    "action": str(metadata.get("action") or row[4] or "moderation"),
                    "record_type": str(metadata.get("record_type") or ("incident" if row[6] == "security_incident" else "case")),
                    "reviewable": str(metadata.get("case_id") or "").isdigit(),
                    "target_id": str(metadata.get("target_id") or ""),
                    "target_name": str(metadata.get("target_name") or "—"),
                    "reason": str(metadata.get("reason") or "No reason provided"),
                    "outcome": str(metadata.get("outcome") or "success"),
                    "details": str(metadata.get("details") or ""),
                    "expires_at": format_timestamp(metadata["expires_at"]) if str(metadata.get("expires_at") or "").isdigit() else None,
                })
            review_by_case = {
                str(row[0]): {"reviewed_by": str(row[1]), "reviewer_name": str(row[2]), "reviewed_at": row[3]}
                for row in review_rows
            }
            for case in cases:
                review = review_by_case.get(case["case_id"])
                case["reviewed"] = bool(review)
                case["reviewer_name"] = review["reviewer_name"] if review else ""
                case["reviewed_at"] = review["reviewed_at"] if review else None
        except psycopg.Error as exc:
            app.logger.warning("Could not load guild moderation history: %s", type(exc).__name__)
            moderation_error = "Moderation history is temporarily unavailable."

    return render_template(
        "guild_moderation.html",
        guild=guild,
        cases=cases,
        moderation_error=moderation_error,
        can_review_incidents=can_review_incidents,
    )


@app.post("/api/dashboard/<guild_id>/incidents/<case_id>/review")
@login_required
def review_security_incident(guild_id, case_id):
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not user_is_guild_admin(guild_id):
        return jsonify({"ok": False, "error": "Administrator permission is required to review security incidents."}), 403
    if not valid_admin_csrf():
        return jsonify({"ok": False, "error": "Refresh the page and try again."}), 400
    if not DATABASE_URL or not case_id.isdigit() or len(case_id) > 22:
        return jsonify({"ok": False, "error": "That security incident could not be found."}), 404
    try:
        with db_connect() as conn:
            incident_rows = conn.execute(
                "SELECT metadata FROM bot_telemetry WHERE guild_id=%s AND event_type='security_incident' ORDER BY id DESC LIMIT 500",
                (str(guild_id),),
            ).fetchall()
            exists = False
            for row in incident_rows:
                try:
                    metadata = json.loads(row[0] or "{}")
                except (TypeError, ValueError):
                    continue
                if isinstance(metadata, dict) and str(metadata.get("case_id") or "") == case_id:
                    exists = True
                    break
            if not exists:
                return jsonify({"ok": False, "error": "That security incident could not be found."}), 404
            user = session.get("user") or {}
            reviewer_id = current_discord_user_id()
            reviewer_name = str(user.get("global_name") or user.get("username") or "Server administrator")[:100]
            note = str(request.form.get("note") or "").strip()[:500]
            row = conn.execute(
                "INSERT INTO security_incident_reviews(guild_id,case_id,reviewed_by,reviewer_name,note) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(guild_id,case_id) DO UPDATE SET reviewed_by=EXCLUDED.reviewed_by,reviewer_name=EXCLUDED.reviewer_name,reviewed_at=NOW(),note=EXCLUDED.note "
                "RETURNING reviewed_at",
                (str(guild_id), case_id, reviewer_id, reviewer_name, note),
            ).fetchone()
        reviewed_at = row[0].isoformat() if row and row[0] else ""
        return jsonify({"ok": True, "reviewed": True, "reviewer_name": reviewer_name, "reviewed_at": reviewed_at})
    except psycopg.Error as exc:
        app.logger.warning("Could not record security incident review: %s", type(exc).__name__)
        return jsonify({"ok": False, "error": "The review could not be saved right now."}), 503


@app.get("/api/dashboard/<guild_id>/resources")
@login_required
def dashboard_resources(guild_id):
    """Return bot-authorized guild resources from the signed bridge heartbeat."""
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    try:
        guild = next(
            (item for item in bot_guild_snapshot() if str(item.get("id")) == str(guild_id)),
            None,
        )
        if not guild:
            return jsonify({"ok": False, "error": "Gargand is offline or is not connected to this server. Refresh after the bot checks in."}), 503
        # Discord's guild channels/roles endpoints require bot authorization. The website's
        # OAuth token only grants access to the user's profile and guild list, so use the
        # channels/roles supplied by the bot over the authenticated heartbeat instead.
        if "channels" not in guild or "roles" not in guild:
            return jsonify({"ok": False, "error": "The bot is online, but its resource list is outdated. Wait for the latest bot deployment and refresh this page."}), 503
        channel_items = [
            {"id": str(item.get("id", "")), "name": str(item.get("name", "")),
             "type": int(item.get("type", 0)), "position": int(item.get("position", 0))}
            for item in guild.get("channels", [])
            if isinstance(item, dict) and str(item.get("id", "")).isdigit()
            and int(item.get("type", 0)) in {0, 2, 4, 5, 13, 15}
        ]
        role_items = [
            {"id": str(item.get("id", "")), "name": str(item.get("name", "")),
             "position": int(item.get("position", 0))}
            for item in guild.get("roles", [])
            if isinstance(item, dict) and str(item.get("id", "")).isdigit()
            and str(item.get("id")) != str(guild_id)
        ]
        channel_items.sort(key=lambda item: (item["position"], item["name"].casefold()))
        role_items.sort(key=lambda item: (-item["position"], item["name"].casefold()))
        return jsonify({"ok": True, "channels": channel_items, "roles": role_items})
    except (ValueError, TypeError, psycopg.Error) as exc:
        app.logger.warning("Could not load dashboard resources: %s", type(exc).__name__)
        return jsonify({"ok": False, "error": "Could not load Discord channels and roles. Try refreshing after the bot checks in."}), 503


@app.post("/api/dashboard/<guild_id>/settings")
@login_required
def update_settings(guild_id):
    if not user_can_manage_guild(guild_id):
        return jsonify({"ok": False, "error": "You do not have permission to manage this server."}), 403
    if not bot_online() or not any(item["id"] == str(guild_id) for item in bot_guild_snapshot()):
        return jsonify({"ok": False, "error": "Gargand is offline or is not connected to this server."}), 503
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return jsonify({"ok": False, "error": "Choose at least one setting to update."}), 400
    clean = {}
    guild_settings = next((item.get("settings", {}) for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {}) or {}
    anti_nuke_defaults = {
        "anti_nuke": False,
        "anti_nuke_auto_lockdown": False,
        "anti_nuke_auto_ban": False,
        "anti_nuke_trusted_role_ids": [],
        "anti_nuke_window_seconds": 10,
        "anti_nuke_threshold_channel_delete": 3,
        "anti_nuke_threshold_role_delete": 3,
        "anti_nuke_threshold_channel_update": 4,
        "anti_nuke_threshold_role_update": 4,
    }
    anti_nuke_changed = False
    for key, value in payload.items():
        if not key.startswith("anti_nuke"):
            continue
        current = guild_settings.get(key, anti_nuke_defaults.get(key))
        if key == "anti_nuke_trusted_role_ids":
            current = sorted(str(item) for item in current) if isinstance(current, (list, tuple, set)) else []
            submitted = sorted(str(item) for item in value) if isinstance(value, list) else value
        elif key in ANTI_NUKE_NUMERIC_RANGES:
            try:
                current = int(current)
            except (TypeError, ValueError):
                current = anti_nuke_defaults[key]
            submitted = value
        else:
            current = bool(current)
            submitted = value
        if submitted != current:
            anti_nuke_changed = True
            break
    if anti_nuke_changed and not user_is_guild_admin(guild_id):
        return jsonify({"ok": False, "error": "Administrator permission is required to change anti-nuke settings."}), 403
    for key, value in payload.items():
        if key not in EDITABLE_SETTINGS:
            return jsonify({"ok": False, "error": f"Unsupported setting: {key}."}), 400
        if key == "anti_nuke_trusted_role_ids":
            if not isinstance(value, list) or len(value) > 20:
                return jsonify({"ok": False, "error": "Choose up to 20 trusted roles."}), 400
            role_ids = list(dict.fromkeys(str(item).strip() for item in value))
            if any(not item.isdigit() or len(item) > 22 for item in role_ids):
                return jsonify({"ok": False, "error": "Trusted roles must be selected from this server."}), 400
            try:
                roles_response = requests.get(f"{DISCORD_API}/guilds/{guild_id}/roles", headers=discord_headers(), timeout=12)
                if roles_response.status_code != 200:
                    return jsonify({"ok": False, "error": "Discord could not verify the selected trusted roles."}), 502
                valid_role_ids = {str(role.get("id")) for role in roles_response.json() if isinstance(role, dict) and str(role.get("id")) != str(guild_id)}
                if any(item not in valid_role_ids for item in role_ids):
                    return jsonify({"ok": False, "error": "One or more trusted roles do not belong to this server."}), 400
            except (requests.RequestException, ValueError, TypeError):
                return jsonify({"ok": False, "error": "Discord could not verify the selected trusted roles."}), 502
            clean[key] = role_ids
        elif key in AUTOMOD_NUMERIC_RANGES:
            minimum, maximum = AUTOMOD_NUMERIC_RANGES[key]
            if type(value) is not int or not minimum <= value <= maximum:
                return jsonify({"ok": False, "error": f"{key.replace('_', ' ')} must be between {minimum} and {maximum}."}), 400
            clean[key] = value
        elif key in ANTI_NUKE_NUMERIC_RANGES:
            minimum, maximum = ANTI_NUKE_NUMERIC_RANGES[key]
            if type(value) is not int or not minimum <= value <= maximum:
                return jsonify({"ok": False, "error": f"{key.replace('_', ' ')} must be between {minimum} and {maximum}."}), 400
            clean[key] = value
        elif key in CHANNEL_SETTINGS | ROLE_SETTINGS | {"appeal_server_id"}:
            raw = str(value or "").strip()
            if raw and (not raw.isdigit() or len(raw) > 22):
                return jsonify({"ok": False, "error": f"{key.replace('_', ' ')} must be a numeric Discord ID."}), 400
            if raw and key in CHANNEL_SETTINGS:
                guild_snapshot = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {})
                channels = guild_snapshot.get("channels", [])
                selected = next((item for item in channels if isinstance(item, dict) and str(item.get("id")) == raw), None)
                if selected is None:
                    return jsonify({"ok": False, "error": f"Select a channel that belongs to this server for {key.replace('_', ' ')}."}), 400
                channel_type = selected.get("type")
                if key.endswith("_category_id"):
                    valid_type = channel_type == 4
                else:
                    valid_type = channel_type in {0, 5}
                if not valid_type:
                    expected = "a category" if key.endswith("_category_id") else "a text channel"
                    return jsonify({"ok": False, "error": f"Choose {expected} for {key.replace('_', ' ')}."}), 400
            elif raw and key in ROLE_SETTINGS:
                guild_snapshot = next((item for item in bot_guild_snapshot() if item["id"] == str(guild_id)), {})
                roles = guild_snapshot.get("roles", [])
                if not any(isinstance(item, dict) and str(item.get("id")) == raw for item in roles):
                    return jsonify({"ok": False, "error": "Select a role that belongs to this server."}), 400
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
        elif key == "automod_punishment":
            raw = str(value or "delete").strip().lower()
            if raw not in {"delete", "timeout"}:
                return jsonify({"ok": False, "error": "Auto-Mod punishment must be delete or timeout."}), 400
            clean[key] = raw
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
        return jsonify({"ok": False, "error": "Gargand is offline or is not connected to this server."}), 503
    payload = request.get_json(silent=True) or {}
    allowed_actions = {"sync_setup", "post_ticket_panel", "post_verification_panel", "post_feedback_panel", "post_application_panel", "toggle_jail", "raid_lockdown", "raid_release"}
    if payload.get("action") not in allowed_actions:
        return jsonify({"ok": False, "error": "Unknown action."}), 400
    if payload.get("action") in {"raid_lockdown", "raid_release"} and not user_is_guild_admin(guild_id):
        return jsonify({"ok": False, "error": "Administrator permission is required for raid lockdown controls."}), 403
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
def premium_vault():
    return redirect(url_for("index"))


@app.get("/redeem")
def redeem():
    return redirect(url_for("index"))


@app.get("/health")
def health():
    # Keep Render's process health check independent from optional integrations,
    # while making database configuration/connectivity observable without secrets.
    database_configured = bool(DATABASE_URL)
    database_reachable = False
    if database_configured:
        try:
            with db_connect() as conn:
                conn.execute("SELECT 1").fetchone()
            database_reachable = True
        except psycopg.Error as exc:
            app.logger.warning("Health check could not reach database: %s", type(exc).__name__)
    with APP_METRICS_LOCK:
        request_count = APP_REQUEST_COUNT
    return jsonify({
        "ok": True,
        "service": "Gargand Dashboard",
        "uptime_seconds": max(0, int(time.time() - APP_STARTED_AT)),
        "requests_since_start": request_count,
        "configuration": {
            "stable_session_secret_configured": bool(
                (os.getenv("SESSION_SECRET") or os.getenv("ROBLOX_OAUTH_CLIENT_SECRET") or "").strip()
            ),
            "discord_oauth_configured": bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET),
            "bot_bridge_secret_configured": bool(BOT_BRIDGE_SECRET),
        },
        "database": {
            "configured": database_configured,
            "reachable": database_reachable,
        },
    })



ACHIEVEMENTS = [
    ("first_steps", "🌱 First Steps", "Earn your first 100 XP.", 100),
    ("night_walker", "🌙 Night Walker", "Reach level 5.", 500),
    ("veteran", "⭐ Gargand Veteran", "Reach 10,000 XP.", 10000),
    ("secret_hunter", "🥚 Secret Hunter", "Discover 10 Gargand secrets.", 0),
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
    if xp >= 500: badges.append(("⭐", "Gargand Veteran", "Reach 500 XP."))
    if xp >= 1000: badges.append(("👑", "Gargand Legend", "Reach 1,000 XP."))
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

COMMANDS = [
    ("!help", "Utility", "Show the bot's command help."),
    ("!questions", "Utility", "Answer common questions about Gargand, setup, logging, security, tickets and the website dashboard."),
    ("!about", "Utility", "Show Gargand's launch description: 1.0v LAUNCH."),
    ("!setup", "Admin tools", "Open the interactive server setup dashboard and configure features there."),
    ("!setup templates", "Admin tools", "Choose a Community, Gaming, Creator, or Support server starter layout with ready-to-edit rules and channels."),
    ("!ban @member [reason]", "Moderation", "Ban a member. Staff only."),
    ("!kick @member [reason]", "Moderation", "Kick a member. Staff only."),
    ("!warn @member [reason]", "Moderation", "Warn a member. Staff only."),
    ("!report @member <reason>", "Community", "Send a member report to the configured staff log channel; the report is saved as a moderation case."),
    ("!purge <amount>", "Moderation", "Delete recent messages. Alias: !clear."),
    ("!warnings @member", "Moderation", "Show a member's warning record. Alias: !warns."),
    ("!clearwarnings @member", "Moderation", "Clear a member's warning record. Alias: !resetwarnings."),
    ("!timeout @member <duration> [reason]", "Moderation", "Temporarily timeout a member."),
    ("!case <id>", "Moderation", "Look up a saved moderation case or security incident."),
    ("!cases [@member]", "Moderation", "List recent cases, optionally filtered to one member."),
    ("!lock", "Moderation", "Lock the current channel."),
    ("!unlock", "Moderation", "Unlock the current channel."),
    ("!antispam <true|false>", "Security", "Enable or disable burst-spam protection; the dashboard Auto-Mod spam setting also controls it.") ,
    ("!raidlockdown [duration]", "Security", "Admin-only, temporary server posting lockdown with automatic permission restore; maximum one hour."),
    ("!raidrelease", "Security", "Restore the saved channel permissions and end a Gargand raid lockdown."),
    ("!slowmode <seconds>", "Moderation", "Set channel slowmode. Alias: !slow."),
    ("!jail @member [reason]", "Moderation", "Jail a member using the configured jail system."),
    ("!unjail @member [reason]", "Moderation", "Release a jailed member."),
    ("!announce #channel <message>", "Admin tools", "Post a server announcement."),
    ("!poll <question> | <option1> | <option2> [...]", "Community", "Staff can create a reaction poll with two to ten options separated by vertical bars."),
    ("!afk [reason]", "Utility", "Set your AFK status."),
    ("!8ball <question>", "Fun", "Ask the Gargand 8-Ball a question."),
    ("!mommycount [@member]", "Fun", "Count how many times a member has said “mommy” in this server."),
    ("!swearcount [@member]", "Moderation", "Show the number of configured swear-word matches for a member."),
    ("!antiswear <on|off|status>", "Moderation", "Admins can enable or disable the server's configurable anti-swear filter."),
    ("!swearwords <add|remove|list> [word or phrase]", "Moderation", "Admins configure which words or phrases the anti-swear filter watches."),
    ("!choose <option> | <option> ...", "Fun", "Let Gargand pick one of up to 20 options."),
    ("!roll [NdM]", "Fun", "Roll a die, such as `!roll 20` or `!roll 3d8`."),
    ("!rps <rock|paper|scissors>", "Fun", "Play rock, paper, scissors against Gargand."),
    ("!quote", "Fun", "Get a little Gargand wisdom."),
    ("!reverse <text>", "Fun", "Reverse a short line of text."),
    ("!mock <text>", "Fun", "mOcK a short line of text."),
    ("!color <hex>", "Utility", "Preview a six-digit color, such as `!color 8B5CF6`."),
    ("!avatar [@member]", "Utility", "Show your avatar or another member's avatar."),
    ("!userinfo [@member]", "Utility", "Show account, server join, and role details."),
    ("!serverinfo", "Utility", "Show useful information about this server."),
    ("!aiimage <description>", "Creative AI", "Image generation is currently unavailable in the free AI setup. Alias: `!aiart`."),
    ("!ask <question>", "Creative AI", "Ask Gargand AI a general question and get a concise answer."),
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
    ("!appeal case <id> <statement>", "Tickets", "Appeal your own warning or timeout case through a private review ticket."),
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
    ("!level [@member]", "Community", "Show your XP and level or another member's level."),
    ("!leaderboard", "Community", "Show the top 10 members by Gargand XP."),
    ("!suggest <idea>", "Community", "Send a suggestion to the configured staff feedback/suggestions channel."),
    ("!serverstats", "Utility", "Show member counts, channels, server creation date and owner."),
    ("!securitycheck", "Security", "Check Gargand permissions, logging setup and suggestions channel configuration. Staff only."),
    ("!configbackup", "Admin tools", "Export this server's Gargand settings to a JSON file. Administrator only."),
    ("!remind <duration> <message>", "Utility", "Set a persistent reminder from 1 minute to 7 days ahead."),
    # Slash-command directory: keep every existing ! command above and also advertise the new / equivalents.
    ("/help", "Utility", "Show Gargand's command help as a Discord slash command."),
    ("/about", "Utility", "Show Gargand's launch information."),
    ("/setup", "Admin tools", "Open the interactive server setup dashboard."),
    ("/ban @member [reason]", "Moderation", "Ban a member. Staff only."),
    ("/kick @member [reason]", "Moderation", "Kick a member. Staff only."),
    ("/warn @member [reason]", "Moderation", "Warn a member. Staff only."),
    ("/purge <amount>", "Moderation", "Delete recent messages."),
    ("/warnings @member", "Moderation", "Show a member's warning record."),
    ("/clearwarnings @member", "Moderation", "Clear a member's warning record."),
    ("/timeout @member <duration> [reason]", "Moderation", "Temporarily timeout a member."),
    ("/case <id>", "Moderation", "Look up a saved moderation case or security incident."),
    ("/cases [@member]", "Moderation", "List recent cases, optionally filtered to one member."),
    ("/lock", "Moderation", "Lock the current channel."),
    ("/unlock", "Moderation", "Unlock the current channel."),
    ("/raidlockdown [duration]", "Security", "Admin-only temporary posting lockdown with automatic permission restore."),
    ("/raidrelease", "Security", "Restore permissions and end a Gargand raid lockdown."),
    ("/slowmode <seconds>", "Moderation", "Set channel slowmode."),
    ("/jail @member [reason]", "Moderation", "Jail a member using the configured jail system."),
    ("/unjail @member [reason]", "Moderation", "Release a jailed member."),
    ("/announce #channel <message>", "Admin tools", "Post a server announcement."),
    ("/poll <prompt>", "Community", "Create a reaction poll in the format Question | Option 1 | Option 2, with two to ten options."),
    ("/afk [reason]", "Utility", "Set your AFK status."),
    ("/8ball <question>", "Fun", "Ask the Gargand 8-Ball a question."),
    ("/mommycount [@member]", "Fun", "Count tracked uses of mommy in this server."),
    ("/swearcount [@member]", "Moderation", "Show configured swear-word match counts."),
    ("/antiswear <on|off|status>", "Moderation", "Manage the configurable anti-swear filter."),
    ("/swearwords <add|remove|list> [word or phrase]", "Moderation", "Configure filtered words or phrases."),
    ("/choose <option> | <option> ...", "Fun", "Let Gargand pick from up to 20 options."),
    ("/roll [NdM]", "Fun", "Roll dice."),
    ("/rps <rock|paper|scissors>", "Fun", "Play rock, paper, scissors."),
    ("/quote", "Fun", "Get a little Gargand wisdom."),
    ("/reverse <text>", "Fun", "Reverse a short line of text."),
    ("/mock <text>", "Fun", "Mock a short line of text."),
    ("/color <hex>", "Utility", "Preview a six-digit color."),
    ("/avatar [@member]", "Utility", "Show an avatar."),
    ("/userinfo [@member]", "Utility", "Show account and server details."),
    ("/serverinfo", "Utility", "Show server information."),
    ("/ping", "Utility", "Show Gargand latency and online status."),
    ("/membercount", "Utility", "Show total members, humans, and bots."),
    ("/roleinfo @role", "Roles", "Show useful information about a role."),
    ("/channelinfo [#channel]", "Utility", "Show useful information about a text channel."),
    ("/ask <question>", "Creative AI", "Ask Gargand AI a general question."),
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
    ("/appeal case <id> <statement>", "Tickets", "Appeal your own warning or timeout case through a private review ticket."),
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
    ("/level [@member]", "Community", "Show your XP and level or another member's level."),
    ("/leaderboard", "Community", "Show the top 10 members by Gargand XP."),
    ("/suggest <idea>", "Community", "Send a suggestion to the configured staff feedback/suggestions channel."),
    ("/serverstats", "Utility", "Show member counts, channels, server creation date and owner."),
    ("/securitycheck", "Security", "Check Gargand permissions, logging setup and suggestions channel configuration. Staff only."),
    ("/configbackup", "Admin tools", "Export this server's Gargand settings to a JSON file. Administrator only."),
    ("/remind <duration> <message>", "Utility", "Set a persistent reminder from 1 minute to 7 days ahead."),
    ("!ping", "Utility", "Check Gargand bot latency and response health."),
    ("!membercount", "Utility", "Show the current server member count."),
    ("!roleinfo @role", "Utility", "Show details about a server role."),
    ("!channelinfo #channel", "Utility", "Show details about a text channel."),
    ("!recover <case_id>", "Moderation", "Recover or re-check a saved moderation case. Staff only."),
    ("!antinuke", "Security", "Show the current anti-nuke protection status."),
    ("!diagnose", "Admin tools", "Run Gargand setup and website-bridge diagnostics. Staff/admin only."),
    ("!official <action> [value]", "Admin tools", "Check or update supported official-server announcement settings. Restricted to authorized admins."),
    ("!coinflip <bet> <heads|tails>", "Economy", "Bet server coins on a coin flip, if the economy is enabled."),
    ("!highlow <bet>", "Economy", "Play the high-low card game using server coins."),
    ("!blackjack <bet>", "Economy", "Play blackjack using server coins."),
    ("!roulette <bet> <pick>", "Economy", "Play the roulette game using server coins."),
    # New voice music player commands (prefix commands to preserve Discord slash-command capacity).
    ("!join", "Music", "Connect Gargand to the voice channel you are currently in."),
    ("!play <song or URL>", "Music", "Search for a track or play a supported URL in your voice channel."),
    ("!skip", "Music", "Skip the currently playing track."),
    ("!pause", "Music", "Pause music playback."),
    ("!resume", "Music", "Resume paused music playback."),
    ("!stop", "Music", "Stop playback and clear the music queue."),
    ("!queue", "Music", "Show the current track and upcoming songs."),
    ("!nowplaying", "Music", "Show the currently playing track, duration and requester."),
    ("!volume <5-150>", "Music", "Set music volume between 5% and 150%."),
    ("!leave", "Music", "Disconnect Gargand from voice and clear the queue."),
    # New community, feeds, image search and audit commands.
    ("!achievements [@member]", "Community", "View earned Gargand achievement badges."),
    ("/achievements [@member]", "Community", "View earned Gargand achievement badges."),
    ("!quest", "Community", "View today's quest: send 10 messages for 30 bonus XP."),
    ("/quest", "Community", "View today's quest and progress."),
    ("!season", "Community", "View your points in the current monthly event."),
    ("/season", "Community", "View your points in the current monthly event."),
    ("!seasonleaderboard", "Community", "Show the monthly seasonal-event leaderboard."),
    ("/seasonleaderboard", "Community", "Show the monthly seasonal-event leaderboard."),
    ("!globalleaderboard", "Community", "Show top members by combined XP across servers."),
    ("/globalleaderboard", "Community", "Show top members by combined XP across servers."),
    ("!party create <name>", "Co-op", "Create a party and join it."),
    ("/party create <name>", "Co-op", "Create a party and join it."),
    ("!party join <name>", "Co-op", "Join an existing co-op party."),
    ("/party join <name>", "Co-op", "Join an existing co-op party."),
    ("!party leave", "Co-op", "Leave your current co-op party."),
    ("/party leave", "Co-op", "Leave your current co-op party."),
    ("!party status", "Co-op", "View party membership and current-season team points."),
    ("/party status", "Co-op", "View party membership and current-season team points."),
    ("!party leaderboard", "Co-op", "Rank co-op parties by current-season points."),
    ("/party leaderboard", "Co-op", "Rank co-op parties by current-season points."),
    ("!image <search terms>", "Search", "Open results across Google, Bing, DuckDuckGo, Brave and Wikimedia Commons."),
    ("/image <search terms>", "Search", "Open results across multiple image providers."),
    ("!rss add <feed URL>", "Feeds", "Subscribe the current channel to a public RSS or Atom feed."),
    ("/rss add <feed URL>", "Feeds", "Subscribe the current channel to a public RSS or Atom feed."),
    ("!rss list", "Feeds", "List RSS/Atom subscriptions configured for this server."),
    ("/rss list", "Feeds", "List RSS/Atom subscriptions configured for this server."),
    ("!rss remove <ID>", "Feeds", "Remove an RSS/Atom subscription by its ID."),
    ("/rss remove <ID>", "Feeds", "Remove an RSS/Atom subscription by its ID."),
    ("!animewatch <AniList ID>", "Notifications", "Notify this channel when an AniList-tracked anime episode is released."),
    ("/animewatch <AniList ID>", "Notifications", "Notify this channel when an AniList-tracked anime episode is released."),
    ("!animeunwatch <AniList ID>", "Notifications", "Stop episode notifications for an anime in this channel."),
    ("/animeunwatch <AniList ID>", "Notifications", "Stop episode notifications for an anime in this channel."),
    ("!animewatches", "Notifications", "List anime episode notifications configured for this server."),
    ("/animewatches", "Notifications", "List anime episode notifications configured for this server."),
    ("!auditlog [limit]", "Staff audit", "View recent staff-command activity in this server."),
    ("/auditlog [limit]", "Staff audit", "View recent staff-command activity in this server."),
    ("!analytics", "Admin tools", "Show Gargand activity counters for this server. Admin only."),
    ("/analytics", "Admin tools", "Show Gargand activity counters for this server. Admin only.")
]


# Initialize persistent storage on both Gunicorn imports and direct starts.
try:
    init_db()
except psycopg.Error as exc:
    app.logger.error("Database initialization failed: %s", type(exc).__name__)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
