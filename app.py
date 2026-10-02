import os
import secrets
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", secrets.token_hex(32))

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")
BOT_API_URL = os.getenv("BOT_API_URL", "").rstrip("/")
BOT_API_SECRET = os.getenv("BOT_API_SECRET", "")

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


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/commands")
def commands():
    return render_template("commands.html", commands=COMMANDS)


@app.get("/guidelines")
def guidelines():
    return render_template("guidelines.html")


@app.get("/announcements")
def announcements():
    return render_template("announcements.html")


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
]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
