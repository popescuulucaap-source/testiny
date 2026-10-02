import os
import sqlite3
import threading
import requests
import discord
from discord.ext import commands
from flask import Flask, render_template, request, redirect, session, jsonify, url_for

# ---------------------------------------------------------
# 1. DATABASE INITIALIZATION (Prevents missing table crashes)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect("bot_data.sqlite3")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            staff_role_id TEXT,
            log_channel_id TEXT,
            anti_raid INTEGER DEFAULT 0,
            anti_nuke INTEGER DEFAULT 0,
            anti_link INTEGER DEFAULT 0,
            verification_enabled INTEGER DEFAULT 0,
            welcome_channel_id TEXT,
            leave_channel_id TEXT,
            j4j_enabled INTEGER DEFAULT 0,
            daily_coins INTEGER DEFAULT 500,
            booster_role_id TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            reason TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            prize TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# 2. FLASK WEB SERVER SETUP
# ---------------------------------------------------------
web_app = Flask(__name__)
web_app.secret_key = os.getenv("SESSION_SECRET", "testiny_secret_key_123")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5000/callback")
DISCORD_API_BASE = "https://discord.com/api/v10"
BOT_TOKEN = os.getenv("TOKEN")

def get_user_guilds(token):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
    if res.status_code == 200:
        return [g for g in res.json() if (int(g.get("permissions", 0)) & 0x8) == 0x8]
    return []

@web_app.route("/")
def index():
    user = session.get("user")
    guilds = session.get("guilds", [])
    selected_guild = request.args.get("guild_id")
    if not user:
        return redirect(url_for("login"))

    conn = sqlite3.connect("bot_data.sqlite3")
    conn.row_factory = sqlite3.Row
    guild_data = {}
    if selected_guild:
        cur = conn.cursor()
        settings = cur.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (selected_guild,)).fetchone()
        warnings = cur.execute("SELECT * FROM warnings WHERE guild_id = ?", (selected_guild,)).fetchall()
        jails = cur.execute("SELECT * FROM jails WHERE guild_id = ?", (selected_guild,)).fetchall()
        giveaways = cur.execute("SELECT * FROM giveaways WHERE guild_id = ?", (selected_guild,)).fetchall()
        guild_data = {
            "settings": dict(settings) if settings else {},
            "warnings_count": len(warnings),
            "jails": [dict(j) for j in jails],
            "giveaways": [dict(g) for g in giveaways]
        }
    conn.close()
    return render_template("dashboard.html", user=user, guilds=guilds, selected_guild=selected_guild, data=guild_data)

@web_app.route("/login")
def login():
    login_url = (
        f"{DISCORD_API_BASE}/oauth2/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify%20guilds"
    )
    return redirect(login_url)

@web_app.route("/callback")
def callback():
    code = request.args.get("code")
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    res = requests.post(f"{DISCORD_API_BASE}/oauth2/token", data=data)
    token_json = res.json()
    access_token = token_json.get("access_token")
    if not access_token:
        return "Authentication Failed", 400

    user_res = requests.get(f"{DISCORD_API_BASE}/users/@me", headers={"Authorization": f"Bearer {access_token}"})
    session["user"] = user_res.json()
    session["guilds"] = get_user_guilds(access_token)
    return redirect(url_for("index"))

@web_app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@web_app.route("/api/save_settings/<guild_id>", methods=["POST"])
def save_settings(guild_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    payload = request.json
    conn = sqlite3.connect("bot_data.sqlite3")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO guild_settings (
            guild_id, staff_role_id, log_channel_id, anti_raid, anti_nuke, anti_link,
            verification_enabled, welcome_channel_id, leave_channel_id, j4j_enabled, daily_coins
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            staff_role_id=excluded.staff_role_id, log_channel_id=excluded.log_channel_id,
            anti_raid=excluded.anti_raid, anti_nuke=excluded.anti_nuke, anti_link=excluded.anti_link,
            verification_enabled=excluded.verification_enabled, welcome_channel_id=excluded.welcome_channel_id,
            leave_channel_id=excluded.leave_channel_id, j4j_enabled=excluded.j4j_enabled,
            daily_coins=excluded.daily_coins
    """, (
        guild_id, payload.get("staff_role_id"), payload.get("log_channel_id"),
        1 if payload.get("anti_raid") else 0, 1 if payload.get("anti_nuke") else 0,
        1 if payload.get("anti_link") else 0, 1 if payload.get("verification_enabled") else 0,
        payload.get("welcome_channel_id"), payload.get("leave_channel_id"),
        1 if payload.get("j4j_enabled") else 0, payload.get("daily_coins", 500)
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

def start_web():
    port = int(os.getenv("PORT", 5000))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# ---------------------------------------------------------
# 3. DISCORD BOT SETUP
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot successfully logged in as {bot.user}")

# Add any additional bot commands or event handlers here...

# ---------------------------------------------------------
# 4. ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=start_web, daemon=True).start()
    
    if not BOT_TOKEN:
        raise ValueError("TOKEN environment variable is missing in Render settings!")
        
    bot.run(BOT_TOKEN)
