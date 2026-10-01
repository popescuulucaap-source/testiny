import asyncio
import json
import os
import sqlite3
import time
from typing import Optional

import discord
from discord.ext import commands
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Read sensitive parameters securely from environment variables
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("BOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
SECRET_KEY = os.getenv("SESSION_SECRET", "super-secret-key-change-in-production")
DB_PATH = os.getenv("BOT_DB", "bot_data.sqlite3")

if not TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable.")

# Discord Bot Setup
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=INTENTS,
    help_command=None,
    case_insensitive=True
)

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            data TEXT NOT NULL DEFAULT '{}'
        );
    """)
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    print(f"Logged in as bot: {bot.user} (ID: {bot.user.id})")

# FastAPI Web Server Setup
app = FastAPI(title="Testiny Dashboard")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Ensure static folder exists for fallback
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    db_init()
    asyncio.create_task(bot.start(TOKEN))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login():
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={httpx.URL(REDIRECT_URI)}"
        f"&response_type=code&scope=identify%20guilds"
    )
    return RedirectResponse(discord_auth_url)

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient() as client:
        res = await client.post("https://discord.com/api/v10/oauth2/token", data=data, headers=headers)
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve token from Discord.")
        tokens = res.json()
        
        user_res = await client.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        user_data = user_res.json()

    request.session["user"] = {
        "id": user_data["id"],
        "username": user_data["username"],
        "avatar": f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png" if user_data.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png",
        "access_token": tokens["access_token"]
    }
    return RedirectResponse("/")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/api/me")
async def api_me(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

@app.get("/api/stats")
async def api_stats():
    perms = discord.Permissions(administrator=True).value
    invite = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID or (bot.user.id if bot.user else '')}&scope=bot&permissions={perms}"
    return {
        "guilds": len(bot.guilds),
        "users": sum(g.member_count for g in bot.guilds if g.member_count),
        "invite": invite
    }

@app.get("/api/user/guilds")
async def api_user_guilds(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers={"Authorization": f"Bearer {user['access_token']}"}
        )
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user guilds.")
        guilds = res.json()

    manageable = []
    bot_guild_ids = {g.id for g in bot.guilds}
    perms = discord.Permissions(administrator=True).value

    for g in guilds:
        permissions = int(g.get("permissions", 0))
        if (permissions & 0x8 == 0x8) or (permissions & 0x20 == 0x20):
            g_id = int(g["id"])
            g["bot_present"] = g_id in bot_guild_ids
            g["invite"] = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&scope=bot&permissions={perms}&guild_id={g_id}"
            manageable.append(g)

    return manageable