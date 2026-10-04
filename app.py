import os
import json
import secrets
import threading
import time
from collections import deque
from hmac import compare_digest
from functools import wraps
from urllib.parse import urlencode, urlparse

import requests
import psycopg
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", secrets.token_hex(32))
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

def init_db():
    if not DATABASE_URL:
        return
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS announcements (id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, date TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS suggestions (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, suggestion TEXT NOT NULL, date TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS custom_commands (id BIGSERIAL PRIMARY KEY, command TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_bridge_state (state_id SMALLINT PRIMARY KEY CHECK (state_id = 1), last_seen DOUBLE PRECISION NOT NULL, guilds TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS bot_jobs (job_id BIGSERIAL PRIMARY KEY, guild_id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS reviews (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, rating INTEGER NOT NULL, review TEXT NOT NULL, date TEXT NOT NULL, approved BOOLEAN NOT NULL DEFAULT TRUE)")
        conn.commit()

def load_announcements():
    if not DATABASE_URL:
        return session.get("announcements", [])
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body, date FROM announcements ORDER BY id DESC")
            return [{"id":r[0],"title":r[1],"body":r[2],"date":r[3]} for r in cur.fetchall()]

def save_announcement(title, body):
    date=__import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    if not DATABASE_URL:
        items=session.get("announcements", [])
        items.insert(0,{"title":title,"body":body,"date":date})
        session["announcements"]=items
        return
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO announcements (title, body, date) VALUES (%s, %s, %s)",(title,body,date))
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

@app.get("/")
def index():
    features = [
        ("🛡️","Moderation","Ban, kick, warn, timeout, lock, slowmode and jail."),
        ("🔐","Security","Anti-raid, anti-nuke, anti-link and verification."),
        ("🎫","Tickets","Interactive panels, questions, claims, proof and appeals."),
        ("👋","Community","Welcome, leave, invites, vouches, feedback and boosters."),
        ("🎮","Games","High-Low, Coinflip, Blackjack, Roulette and daily coins."),
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
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="Incorrect admin password.")
    return render_template("admin_login.html")

@app.get("/admin/panel")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
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
    return redirect(url_for("admin"))

@app.post("/admin/announcement")
def admin_announcement():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    title=(request.form.get("title") or "Update").strip()
    body=(request.form.get("body") or "").strip()
    if title and body: save_announcement(title,body)
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
    return render_template("announcements.html", announcements=load_announcements())


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

    me = requests.get(f"{DISCORD_API}/users/@me", headers=discord_headers(), timeout=12)
    if me.status_code != 200:
        session.clear()
        return "Could not read your Discord profile.", 400

    session["user"] = me.json()
    return redirect(url_for("servers"))


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
    return render_template(
        "dashboard.html",
        guild=guild,
        settings=settings,
        bot_error=bot_error,
        setting_groups=SETTING_GROUPS,
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


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "Nightfall Dashboard"})


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
]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
