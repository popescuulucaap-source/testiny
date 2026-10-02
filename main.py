import asyncio
import os
import sqlite3

import discord
from discord.ext import commands
import httpx
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# Environment configuration
TOKEN = os.getenv("TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("BOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
SECRET_KEY = os.getenv("SESSION_SECRET", "super-secret-key-change-in-production")
DB_PATH = os.getenv("BOT_DB", "bot_data.sqlite3")

# Discord Bot Setup
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS, help_command=None)

# Database Helper Functions
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# FastAPI Web App Setup
app = FastAPI(title="Testiny Dashboard")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.on_event("startup")
async def startup_event():
    db_init()
    if TOKEN:
        asyncio.create_task(bot.start(TOKEN))

# Embedded Single-Page Web Interface
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Testiny | Discord Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: { 500: '#6854FF', 600: '#533EFF', 700: '#4122E6' },
                        dark: { 800: '#12141D', 900: '#0B0C10' }
                    }
                }
            }
        }
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-dark-900 text-gray-100 min-h-screen font-sans flex flex-col">

    <nav class="border-b border-gray-800 bg-dark-800/60 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-full bg-brand-500 flex items-center justify-center font-bold text-white text-lg">T</div>
                <span class="text-xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">Testiny</span>
            </div>
            <div id="auth-section">
                <a href="/login" class="bg-brand-500 hover:bg-brand-600 px-5 py-2 rounded-xl font-medium transition flex items-center space-x-2">
                    <i class="fa-brands fa-discord"></i>
                    <span>Login with Discord</span>
                </a>
            </div>
        </div>
    </nav>

    <main class="flex-grow max-w-7xl w-full mx-auto px-4 py-10">
        <div class="rounded-3xl bg-gradient-to-r from-brand-700/30 to-purple-900/20 border border-brand-500/20 p-8 mb-10 flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
                <h1 class="text-3xl font-extrabold text-white mb-2">Manage Testiny Bot</h1>
                <p class="text-gray-400">Post announcements and patch notes live to this page.</p>
            </div>
            <a id="invite-btn" href="#" target="_blank" class="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-6 py-3 rounded-xl font-semibold transition">Invite Bot</a>
        </div>

        <!-- Post Announcement Box (Visible after login) -->
        <div id="admin-update-box" class="hidden bg-dark-800 border border-brand-500/30 p-6 rounded-2xl mb-10 shadow-lg">
            <h2 class="text-xl font-bold text-white mb-4 flex items-center space-x-2">
                <i class="fa-solid fa-bullhorn text-brand-500"></i>
                <span>Post New Bot Update / Announcement</span>
            </h2>
            <form id="update-form" class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Update Title</label>
                    <input type="text" id="update-title" required placeholder="e.g. v1.2 Release - Added Moderation Commands" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-3 text-white focus:outline-none focus:border-brand-500">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Update Content</label>
                    <textarea id="update-content" rows="3" required placeholder="Type details about what was added or changed..." class="w-full bg-dark-900 border border-gray-700 rounded-xl p-3 text-white focus:outline-none focus:border-brand-500"></textarea>
                </div>
                <button type="submit" class="bg-brand-500 hover:bg-brand-600 px-6 py-2.5 rounded-xl font-semibold text-white transition">Publish Update</button>
            </form>
        </div>

        <!-- Live Updates Feed -->
        <section class="space-y-4 mb-10">
            <h2 class="text-2xl font-bold text-white flex items-center space-x-2">
                <i class="fa-solid fa-newspaper text-brand-500"></i>
                <span>Bot Updates & Patch Notes</span>
            </h2>
            <div id="updates-container" class="space-y-4">
                <div class="text-gray-500 py-6 text-center bg-dark-800 rounded-2xl border border-gray-800">
                    Loading updates...
                </div>
            </div>
        </section>
    </main>

    <script>
        async function loadState() {
            try {
                const res = await fetch('/api/stats');
                const stats = await res.json();
                document.getElementById('invite-btn').href = stats.invite || '#';

                const userRes = await fetch('/api/me');
                if (userRes.ok) {
                    const userData = await userRes.json();
                    document.getElementById('auth-section').innerHTML = `
                        <div class="flex items-center space-x-3">
                            <img src="${userData.avatar}" class="w-8 h-8 rounded-full">
                            <span class="font-medium text-white">${userData.username}</span>
                            <a href="/logout" class="text-xs bg-red-500/20 text-red-400 px-3 py-1.5 rounded-lg border border-red-500/30">Logout</a>
                        </div>
                    `;
                    document.getElementById('admin-update-box').classList.remove('hidden');
                }
            } catch (e) {}
            loadUpdates();
        }

        async function loadUpdates() {
            const container = document.getElementById('updates-container');
            try {
                const res = await fetch('/api/updates');
                const updates = await res.json();
                if (updates.length === 0) {
                    container.innerHTML = `<div class="text-gray-500 py-6 text-center bg-dark-800 rounded-2xl border border-gray-800">No updates posted yet. Log in to create your first announcement!</div>`;
                    return;
                }
                container.innerHTML = updates.map(u => `
                    <div class="bg-dark-800 border border-gray-800 p-5 rounded-2xl">
                        <div class="flex justify-between items-center mb-2">
                            <h3 class="text-lg font-bold text-white">${u.title}</h3>
                            <span class="text-xs text-gray-500">${u.timestamp}</span>
                        </div>
                        <p class="text-gray-300 whitespace-pre-line text-sm">${u.content}</p>
                    </div>
                `).join('');
            } catch (e) {
                container.innerHTML = `<div class="text-red-400 py-6 text-center">Failed to load updates.</div>`;
            }
        }

        document.getElementById('update-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('update-title').value;
            const content = document.getElementById('update-content').value;
            const formData = new FormData();
            formData.append('title', title);
            formData.append('content', content);

            const res = await fetch('/api/updates', { method: 'POST', body: formData });
            if (res.ok) {
                document.getElementById('update-title').value = '';
                document.getElementById('update-content').value = '';
                loadUpdates();
            } else {
                alert('Failed to post update.');
            }
        });

        loadState();
    </script>
</body>
</html>"""

# Web Endpoints
@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_TEMPLATE

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
    bot_id = CLIENT_ID or (bot.user.id if bot.user else '')
    invite = f"https://discord.com/oauth2/authorize?client_id={bot_id}&scope=bot&permissions={perms}"
    return {
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "invite": invite
    }

@app.get("/api/updates")
async def get_updates():
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content, timestamp FROM bot_updates ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "title": r["title"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

@app.post("/api/updates")
async def create_update(request: Request, title: str = Form(...), content: str = Form(...)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="You must be logged in.")
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bot_updates (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    return {"status": "success"}
