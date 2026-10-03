import os
import secrets
from functools import wraps
from urllib.parse import urlencode

import requests
import psycopg
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", secrets.token_hex(32))

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://testiny-7wuu.onrender.com/oauth/callback")
BOT_API_URL = os.getenv("BOT_API_URL", "").rstrip("/")
BOT_API_SECRET = os.getenv("BOT_API_SECRET", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
INVITE_URL = os.getenv("INVITE_URL", "#")
SUPPORT_URL = os.getenv("SUPPORT_URL", "#")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20


def discord_headers():
    return {"Authorization": f"Bearer {session['access_token']}"}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "access_token" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def bot_request(method, path, **kwargs):
    if not BOT_API_URL:
        return {"ok": False, "error": "BOT_API_URL is not configured."}, 503
    headers = kwargs.pop("headers", {})
    headers["X-Testiny-API-Key"] = BOT_API_SECRET
    headers["Content-Type"] = "application/json"
    try:
        r = requests.request(method, f"{BOT_API_URL}{path}", headers=headers, timeout=12, **kwargs)
        data = r.json() if r.content else {}
        return data, r.status_code
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Bot API unavailable: {exc}"}, 502


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
            cur.execute("CREATE TABLE IF NOT EXISTS custom_commands (id BIGSERIAL PRIMARY KEY, command TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL)")
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
    commands=list(COMMANDS)
    commands.extend((x["command"],x["category"],x["description"]) for x in load_custom_commands())
    return commands

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
    ]
    return render_template("index.html", features=features)

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
    return render_template("admin.html", announcements=load_announcements())

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
        if (int(g.get("permissions", "0")) & MANAGE_GUILD) == MANAGE_GUILD
    ]
    bot_data, _ = bot_request("GET", "/guilds")
    bot_ids = {str(x.get("id")) for x in bot_data.get("guilds", [])} if isinstance(bot_data, dict) else set()
    for guild in guilds:
        guild["bot_present"] = guild["id"] in bot_ids
        icon_hash = guild.get("icon")
        guild["icon_url"] = f"https://cdn.discordapp.com/icons/{guild['id']}/{icon_hash}.png?size=128" if icon_hash else ""
    return render_template("servers.html", guilds=guilds)


@app.get("/dashboard/<guild_id>")
@login_required
def dashboard(guild_id):
    guilds_r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=discord_headers(), timeout=12)
    if guilds_r.status_code != 200:
        return redirect(url_for("login"))
    guild = next((g for g in guilds_r.json() if g["id"] == guild_id), None)
    if not guild or (int(guild.get("permissions", "0")) & MANAGE_GUILD) != MANAGE_GUILD:
        return "You do not have permission to manage this server.", 403

    settings, status = bot_request("GET", f"/guilds/{guild_id}/settings")
    return render_template(
        "dashboard.html",
        guild=guild,
        settings=settings if status == 200 else {},
        bot_error=None if status == 200 else settings.get("error"),
    )


@app.post("/api/dashboard/<guild_id>/settings")
@login_required
def update_settings(guild_id):
    payload = request.get_json(silent=True) or {}
    data, status = bot_request("POST", f"/guilds/{guild_id}/settings", json=payload)
    return jsonify(data), status


@app.post("/api/dashboard/<guild_id>/action")
@login_required
def dashboard_action(guild_id):
    payload = request.get_json(silent=True) or {}
    data, status = bot_request("POST", f"/guilds/{guild_id}/actions", json=payload)
    return jsonify(data), status


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "Testiny Dashboard"})


COMMANDS = [
    ("!setup", "Server setup", "Open Testiny's interactive configuration system."),
    ("!ban @user", "Moderation", "Ban a member and provide the configured appeal route."),
    ("!kick @user", "Moderation", "Kick a member from the server."),
    ("!warn @user", "Moderation", "Issue a warning. Five warnings trigger the configured kick behavior."),
    ("!timeout @user <duration>", "Moderation", "Temporarily timeout a member."),
    ("!lock", "Moderation", "Lock the current channel."),
    ("!slowmode <seconds>", "Moderation", "Configure channel slowmode."),
    ("!jail @user <reason>", "Jail", "Move a member into the configured jail system."),
    ("!unjail @user", "Jail", "Release a jailed member and restore their roles."),
    ("!afk <reason>", "Utility", "Set an AFK reason and protect the user from repeated pings."),
    ("!role give @user @role", "Roles", "Give a role to a member or everyone where permitted."),
    ("!role make <name> #HEX", "Roles", "Create a role with a chosen color."),
    ("!invites @user", "Invites", "Show invite categories and tracked invite counts."),
    ("!invited @user", "Invites", "List clean users invited by a member."),
    ("!inviter @user", "Invites", "Show the recorded inviter."),
    ("!reset invites @user", "Invites", "Reset invite tracking for one user."),
    ("!reset invites @everyone", "Invites", "Reset invite tracking for everyone."),
    ("!vouch @user", "Community", "Create a formatted vouch entry in the configured channel."),
    ("!proof please", "Proof", "Send a proof request into the configured proof flow."),
    ("!highlow", "Games", "Play High-Low."),
    ("!coinflip", "Games", "Play Coinflip."),
    ("!blackjack", "Games", "Play Blackjack."),
    ("!roulette", "Games", "Play Roulette."),
    ("!daily", "Games", "Claim the daily 500-coin reward."),
    ("!giveaway", "Giveaways", "Create a giveaway with prize, timer and winners."),
    ("!giveaway reroll MESSAGE_ID", "Giveaways", "Reroll a completed giveaway."),
    ("!giveaway end MESSAGE_ID", "Giveaways", "End a giveaway early."),
    ("!stick", "Utility", "Create a sticky message."),
    ("!unstick", "Utility", "Remove the sticky message."),
    ("!autoreaction #channel emoji", "Utility", "Automatically react to messages in a channel."),
    ("!welcome setup", "Community", "Configure welcome channel, invite attribution and member-count embeds."),
    ("!leave setup", "Community", "Configure goodbye messages and invite attribution."),
    ("!autorole setup", "Community", "Assign a configured role to new members."),
    ("!antiraid setup", "Security", "Enable raid protections and external-app restrictions."),
    ("!antinuke setup", "Security", "Configure channel-deletion and permission protection."),
    ("!antilink setup", "Security", "Automatically timeout link messages while allowing GIFs."),
    ("!verify setup", "Security", "Create the verified/unverified flow with private challenge verification."),
    ("!commandchannel setup", "Security", "Restrict prefix commands to a configured channel."),
    ("!feedback setup", "Community", "Create an interactive feedback and star-rating panel."),
    ("!j4j setup", "Community", "Configure J4J detection, DM prompts and J4J tickets."),
    ("!boost setup", "Community", "Configure booster role and boost announcements."),
    ("!application setup", "Community", "Configure staff/application panels."),
    ("!ticket setup", "Tickets", "Configure ticket types, questions, categories, claims and staff pings."),
    ("!appeal setup", "Tickets", "Configure the appeal server/link used by moderation."),
    ("!gamble setup", "Games", "Configure the gambling channel and economy."),
]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
