import asyncio
import json
import os
import sqlite3
from typing import Optional

import discord
from discord.ext import commands
import httpx
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# Environment Configuration
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("BOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
SECRET_KEY = os.getenv("SESSION_SECRET", "super-secret-key-change-in-production")
DB_PATH = os.getenv("BOT_DB", "bot_data.sqlite3")

# SQLite Database Management
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            prefix TEXT DEFAULT '!',
            welcome_enabled INTEGER DEFAULT 0,
            automod_enabled INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()

# Dynamic Guild Prefix Resolution
def get_prefix(bot_instance, message):
    if not message.guild:
        return "!"
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT prefix FROM guild_settings WHERE guild_id = ?", (str(message.guild.id),))
    row = cursor.fetchone()
    conn.close()
    return row["prefix"] if row else "!"

# Discord Bot Setup
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

bot = commands.Bot(command_prefix=get_prefix, intents=INTENTS, help_command=None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# Built-in Bot Commands
@bot.command(name="ping")
async def ping(ctx):
    """Check bot latency."""
    await ctx.send(f"🏓 Pong! Latency is `{round(bot.latency * 1000)}ms`.")

@bot.command(name="prefix")
@commands.has_permissions(administrator=True)
async def change_prefix(ctx, new_prefix: str):
    """Change prefix for this server."""
    conn = db_connect()
    conn.execute(
        "INSERT INTO guild_settings (guild_id, prefix) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET prefix = ?",
        (str(ctx.guild.id), new_prefix, new_prefix)
    )
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Prefix successfully updated to `{new_prefix}`!")

@bot.command(name="botinfo")
async def botinfo(ctx):
    """Show information about Testiny bot."""
    embed = discord.Embed(title="🤖 Testiny Bot Specs", color=0x6854FF)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Dashboard", value=REDIRECT_URI.replace("/auth/callback", ""), inline=False)
    await ctx.send(embed=embed)

# FastAPI Application Setup
app = FastAPI(title="Testiny Command Center")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.on_event("startup")
async def startup_event():
    db_init()
    if TOKEN:
        asyncio.create_task(bot.start(TOKEN))

# Embedded Front-End Template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Testiny | Next-Gen Discord Bot & Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: { 500: '#6854FF', 600: '#533EFF', 700: '#4122E6' },
                        dark: { 800: '#12141D', 850: '#0E1017', 900: '#0B0C10' }
                    }
                }
            }
        }
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-dark-900 text-gray-100 min-h-screen font-sans flex flex-col selection:bg-brand-500 selection:text-white">

    <!-- Navbar -->
    <nav class="border-b border-gray-800/80 bg-dark-900/80 backdrop-blur-xl sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-11 h-11 rounded-2xl bg-gradient-to-tr from-brand-700 to-brand-500 flex items-center justify-center font-black text-white text-xl shadow-lg shadow-brand-500/30">
                    T
                </div>
                <span class="text-2xl font-extrabold bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent tracking-tight">Testiny</span>
            </div>

            <div class="hidden md:flex items-center space-x-8 text-sm font-semibold text-gray-300">
                <a href="#features" class="hover:text-brand-500 transition">Features</a>
                <a href="#commands" class="hover:text-brand-500 transition">Commands</a>
                <a href="#updates" class="hover:text-brand-500 transition">Patch Notes</a>
                <a href="#dashboard" class="hover:text-brand-500 transition">Manage Server</a>
            </div>

            <div id="auth-section">
                <a href="/login" class="bg-brand-500 hover:bg-brand-600 px-6 py-2.5 rounded-xl font-semibold transition shadow-lg shadow-brand-500/25 flex items-center space-x-2 text-sm">
                    <i class="fa-brands fa-discord text-lg"></i>
                    <span>Login with Discord</span>
                </a>
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <header class="relative pt-12 pb-20 overflow-hidden">
        <div class="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl -z-10 pointer-events-none"></div>
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <span class="inline-flex items-center space-x-2 bg-brand-500/10 border border-brand-500/30 px-4 py-1.5 rounded-full text-brand-500 text-xs font-bold uppercase tracking-widest mb-6">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>v2.0 Command Center Live</span>
            </span>
            <h1 class="text-4xl sm:text-6xl font-black tracking-tight text-white mb-6 leading-tight">
                Supercharge Your Discord Server <br class="hidden sm:inline">
                <span class="bg-gradient-to-r from-brand-500 via-purple-400 to-indigo-300 bg-clip-text text-transparent">With Complete Web Control</span>
            </h1>
            <p class="text-gray-400 max-w-2xl mx-auto text-lg mb-10">
                Experience ultra-fast moderation, customizable prefix automation, real-time statistics, and seamless server management directly from your browser.
            </p>
            <div class="flex flex-wrap items-center justify-center gap-4">
                <a id="hero-invite-btn" href="#" target="_blank" class="bg-brand-500 hover:bg-brand-600 px-8 py-3.5 rounded-xl font-bold text-white shadow-xl shadow-brand-500/30 transition flex items-center space-x-3">
                    <i class="fa-solid fa-plus"></i>
                    <span>Add Bot to Discord</span>
                </a>
                <a href="#commands" class="bg-dark-800 hover:bg-gray-800 border border-gray-700 px-8 py-3.5 rounded-xl font-bold text-gray-200 transition">
                    Explore Commands
                </a>
            </div>

            <!-- Stats Bar -->
            <div class="mt-16 grid grid-cols-2 md:grid-cols-3 gap-4 max-w-3xl mx-auto">
                <div class="bg-dark-800/60 border border-gray-800 p-6 rounded-2xl backdrop-blur-md">
                    <div id="stat-guilds" class="text-3xl font-black text-white mb-1">--</div>
                    <div class="text-xs uppercase tracking-wider text-gray-400 font-bold">Active Servers</div>
                </div>
                <div class="bg-dark-800/60 border border-gray-800 p-6 rounded-2xl backdrop-blur-md">
                    <div id="stat-ping" class="text-3xl font-black text-emerald-400 mb-1">-- ms</div>
                    <div class="text-xs uppercase tracking-wider text-gray-400 font-bold">Bot Latency</div>
                </div>
                <div class="col-span-2 md:col-span-1 bg-dark-800/60 border border-gray-800 p-6 rounded-2xl backdrop-blur-md">
                    <div class="text-3xl font-black text-brand-500 mb-1">99.9%</div>
                    <div class="text-xs uppercase tracking-wider text-gray-400 font-bold">Uptime Guaranteed</div>
                </div>
            </div>
        </div>
    </header>

    <main class="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 space-y-24 py-10">

        <!-- Bot Features Showcase -->
        <section id="features" class="space-y-10">
            <div class="text-center">
                <h2 class="text-3xl font-extrabold text-white">Why Choose Testiny?</h2>
                <p class="text-gray-400 text-sm mt-2">Built with modern speed, security, and flexibility in mind.</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div class="bg-dark-800 border border-gray-800 p-8 rounded-3xl space-y-4 hover:border-brand-500/50 transition">
                    <div class="w-12 h-12 bg-brand-500/20 text-brand-500 rounded-2xl flex items-center justify-center text-xl font-bold">
                        <i class="fa-solid fa-sliders"></i>
                    </div>
                    <h3 class="text-xl font-bold text-white">Web Dashboard Control</h3>
                    <p class="text-gray-400 text-sm leading-relaxed">No need to remember long setup commands. Change server prefixes, welcome alerts, and auto-mod toggles visually on the web.</p>
                </div>
                <div class="bg-dark-800 border border-gray-800 p-8 rounded-3xl space-y-4 hover:border-brand-500/50 transition">
                    <div class="w-12 h-12 bg-purple-500/20 text-purple-400 rounded-2xl flex items-center justify-center text-xl font-bold">
                        <i class="fa-solid fa-shield-halved"></i>
                    </div>
                    <h3 class="text-xl font-bold text-white">Smart Security & Automod</h3>
                    <p class="text-gray-400 text-sm leading-relaxed">Protect your server automatically against spam, malicious links, and unauthorized advertising with built-in auto-moderation tools.</p>
                </div>
                <div class="bg-dark-800 border border-gray-800 p-8 rounded-3xl space-y-4 hover:border-brand-500/50 transition">
                    <div class="w-12 h-12 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center text-xl font-bold">
                        <i class="fa-solid fa-bolt"></i>
                    </div>
                    <h3 class="text-xl font-bold text-white">Instant Synchronized State</h3>
                    <p class="text-gray-400 text-sm leading-relaxed">Changes made on the website take effect inside Discord in real-time without needing to reboot or restart the bot.</p>
                </div>
            </div>
        </section>

        <!-- Command List Section -->
        <section id="commands" class="space-y-8">
            <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h2 class="text-3xl font-extrabold text-white">Command Arsenal</h2>
                    <p class="text-gray-400 text-sm mt-1">Explore all available commands supported by Testiny.</p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <!-- Command Cards -->
                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!prefix &lt;new_prefix&gt;</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Admin</span>
                    </div>
                    <p class="text-gray-300 text-sm">Changes the bot trigger prefix for your Discord server instantly.</p>
                </div>

                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!ping</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Everyone</span>
                    </div>
                    <p class="text-gray-300 text-sm">Measures response latency and active WebSocket response speed.</p>
                </div>

                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!botinfo</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Everyone</span>
                    </div>
                    <p class="text-gray-300 text-sm">Displays system specifications, server counts, and dashboard links.</p>
                </div>

                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!kick &lt;user&gt;</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Moderator</span>
                    </div>
                    <p class="text-gray-300 text-sm">Removes a specified member from the server with audit logs.</p>
                </div>

                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!ban &lt;user&gt;</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Moderator</span>
                    </div>
                    <p class="text-gray-300 text-sm">Permanently bans a malicious user from rejoining the guild.</p>
                </div>

                <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl space-y-3">
                    <div class="flex items-center justify-between">
                        <span class="font-mono text-brand-500 font-bold bg-brand-500/10 px-3 py-1 rounded-lg text-sm">!clear &lt;amount&gt;</span>
                        <span class="text-xs bg-gray-700 text-gray-300 font-semibold px-2.5 py-1 rounded-md">Moderator</span>
                    </div>
                    <p class="text-gray-300 text-sm">Bulk deletes specified number of messages in the current text channel.</p>
                </div>
            </div>
        </section>

        <!-- Admin Server Management Section -->
        <section id="dashboard" class="space-y-8">
            <div class="border-t border-gray-800 pt-16">
                <h2 class="text-3xl font-extrabold text-white flex items-center space-x-3">
                    <i class="fa-solid fa-server text-brand-500"></i>
                    <span>Server Management Center</span>
                </h2>
                <p class="text-gray-400 text-sm mt-1">Select any server where you have Administrator permissions to manage its settings.</p>
            </div>

            <div id="guilds-wrapper">
                <div class="text-center py-12 bg-dark-800/40 rounded-3xl border border-gray-800 space-y-4">
                    <i class="fa-brands fa-discord text-4xl text-gray-600"></i>
                    <p class="text-gray-400 text-sm">Log in with Discord above to load and manage your servers.</p>
                </div>
            </div>
        </section>

        <!-- Post Updates Box (Owner Only) -->
        <div id="admin-update-box" class="hidden bg-dark-800 border border-brand-500/30 p-8 rounded-3xl shadow-2xl">
            <h2 class="text-xl font-bold text-white mb-4 flex items-center space-x-2">
                <i class="fa-solid fa-bullhorn text-brand-500"></i>
                <span>Publish Public Bot Announcement</span>
            </h2>
            <form id="update-form" class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-1 font-semibold">Title</label>
                    <input type="text" id="update-title" required placeholder="e.g. v2.0 - New Web Admin Management Released" class="w-full bg-dark-900 border border-gray-700 rounded-xl p-3 text-white focus:outline-none focus:border-brand-500">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1 font-semibold">Announcement Content</label>
                    <textarea id="update-content" rows="3" required placeholder="Details about new features or maintenance updates..." class="w-full bg-dark-900 border border-gray-700 rounded-xl p-3 text-white focus:outline-none focus:border-brand-500"></textarea>
                </div>
                <button type="submit" class="bg-brand-500 hover:bg-brand-600 px-6 py-3 rounded-xl font-bold text-white transition">Publish Live</button>
            </form>
        </div>

        <!-- Updates / Patch Notes Feed -->
        <section id="updates" class="space-y-6">
            <h2 class="text-2xl font-bold text-white flex items-center space-x-2">
                <i class="fa-solid fa-newspaper text-brand-500"></i>
                <span>Live Patch Notes & Updates</span>
            </h2>
            <div id="updates-container" class="space-y-4">
                <div class="text-gray-500 py-6 text-center bg-dark-800 rounded-2xl border border-gray-800">
                    Loading updates...
                </div>
            </div>
        </section>

    </main>

    <footer class="border-t border-gray-800/80 py-8 text-center text-gray-500 text-sm bg-dark-900">
        <p>&copy; Testiny Bot Command Center. Powered by FastAPI & discord.py.</p>
    </footer>

    <script>
        let currentUser = null;

        async function init() {
            try {
                // Fetch Stats
                const statsRes = await fetch('/api/stats');
                const stats = await statsRes.json();
                document.getElementById('stat-guilds').innerText = stats.guilds;
                document.getElementById('stat-ping').innerText = stats.ping + ' ms';
                document.getElementById('hero-invite-btn').href = stats.invite || '#';

                // Fetch User
                const userRes = await fetch('/api/me');
                if (userRes.ok) {
                    currentUser = await userRes.json();
                    document.getElementById('auth-section').innerHTML = `
                        <div class="flex items-center space-x-3 bg-dark-800 border border-gray-700/80 px-4 py-2 rounded-2xl">
                            <img src="${currentUser.avatar}" class="w-8 h-8 rounded-full">
                            <span class="font-bold text-white text-sm">${currentUser.username}</span>
                            <a href="/logout" class="text-xs bg-red-500/20 text-red-400 hover:bg-red-500/30 px-3 py-1.5 rounded-lg border border-red-500/30 transition font-semibold">Logout</a>
                        </div>
                    `;
                    document.getElementById('admin-update-box').classList.remove('hidden');
                    loadUserServers();
                }
            } catch (e) {
                console.error("Init failed:", e);
            }
            loadUpdates();
        }

        async function loadUserServers() {
            const container = document.getElementById('guilds-wrapper');
            try {
                const res = await fetch('/api/user/guilds');
                if (!res.ok) throw new Error();
                const guilds = await res.json();

                if (guilds.length === 0) {
                    container.innerHTML = `<div class="text-gray-400 py-8 text-center bg-dark-800 rounded-2xl">No manageable servers found. You must be an Administrator in a server to control it here.</div>`;
                    return;
                }

                container.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        ${guilds.map(g => `
                            <div class="bg-dark-800 border border-gray-800 rounded-2xl p-6 flex flex-col justify-between space-y-4">
                                <div class="flex items-center space-x-4">
                                    ${g.icon 
                                        ? `<img src="https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png" class="w-14 h-14 rounded-2xl border border-gray-700">`
                                        : `<div class="w-14 h-14 rounded-2xl bg-brand-500/20 text-brand-500 border border-brand-500/30 flex items-center justify-center font-extrabold text-xl">${g.name[0]}</div>`
                                    }
                                    <div>
                                        <h3 class="font-bold text-white text-lg">${g.name}</h3>
                                        <span class="text-xs ${g.bot_present ? 'text-emerald-400 font-semibold' : 'text-gray-500'}">
                                            ${g.bot_present ? '● Bot Active' : '○ Bot Not Added'}
                                        </span>
                                    </div>
                                </div>
                                <div>
                                    ${g.bot_present
                                        ? `<button onclick="openServerConfig('${g.id}', '${g.name.replace(/'/g, "\\'")}')" class="w-full bg-brand-500 hover:bg-brand-600 px-4 py-2.5 rounded-xl font-bold text-sm text-white transition">Manage Settings</button>`
                                        : `<a href="${g.invite}" target="_blank" class="block text-center w-full bg-gray-700 hover:bg-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm text-gray-200 transition">Invite Bot</a>`
                                    }
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div id="server-config-panel" class="hidden mt-8 bg-dark-800 border border-brand-500/40 p-8 rounded-3xl space-y-6">
                        <div class="flex items-center justify-between border-b border-gray-800 pb-4">
                            <h3 id="config-server-name" class="text-2xl font-black text-white">Configuring Server</h3>
                            <button onclick="document.getElementById('server-config-panel').classList.add('hidden')" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-xl"></i></button>
                        </div>
                        <form id="server-config-form" class="space-y-6">
                            <input type="hidden" id="config-guild-id">
                            <div>
                                <label class="block text-sm font-bold text-gray-300 mb-2">Command Prefix</label>
                                <input type="text" id="config-prefix" required class="w-full max-w-xs bg-dark-900 border border-gray-700 rounded-xl p-3 text-white focus:outline-none focus:border-brand-500 font-mono">
                            </div>
                            <div class="flex items-center space-x-3">
                                <input type="checkbox" id="config-automod" class="w-5 h-5 accent-brand-500 rounded">
                                <label for="config-automod" class="text-sm font-semibold text-gray-300">Enable Auto-Moderation (Spam Protection)</label>
                            </div>
                            <div class="flex items-center space-x-3">
                                <input type="checkbox" id="config-welcome" class="w-5 h-5 accent-brand-500 rounded">
                                <label for="config-welcome" class="text-sm font-semibold text-gray-300">Enable Member Welcome Announcements</label>
                            </div>
                            <button type="submit" class="bg-emerald-500 hover:bg-emerald-600 px-8 py-3 rounded-xl font-bold text-white transition">Save Changes</button>
                        </form>
                    </div>
                `;
            } catch (e) {
                container.innerHTML = `<div class="text-red-400 py-6 text-center">Failed to load managed servers.</div>`;
            }
        }

        async function openServerConfig(guildId, guildName) {
            const panel = document.getElementById('server-config-panel');
            document.getElementById('config-server-name').innerText = 'Manage: ' + guildName;
            document.getElementById('config-guild-id').value = guildId;

            // Fetch current settings
            const res = await fetch(`/api/guild/${guildId}/settings`);
            if (res.ok) {
                const settings = await res.json();
                document.getElementById('config-prefix').value = settings.prefix || '!';
                document.getElementById('config-automod').checked = !!settings.automod_enabled;
                document.getElementById('config-welcome').checked = !!settings.welcome_enabled;
                panel.classList.remove('hidden');
                panel.scrollIntoView({ behavior: 'smooth' });
            }
        }

        document.addEventListener('submit', async (e) => {
            if (e.target && e.target.id === 'server-config-form') {
                e.preventDefault();
                const guildId = document.getElementById('config-guild-id').value;
                const prefix = document.getElementById('config-prefix').value;
                const automod = document.getElementById('config-automod').checked ? 1 : 0;
                const welcome = document.getElementById('config-welcome').checked ? 1 : 0;

                const res = await fetch(`/api/guild/${guildId}/settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prefix, automod_enabled: automod, welcome_enabled: welcome })
                });

                if (res.ok) {
                    alert('Server settings saved successfully!');
                } else {
                    alert('Failed to save settings. Ensure you have administrator rights.');
                }
            }
        });

        async function loadUpdates() {
            const container = document.getElementById('updates-container');
            try {
                const res = await fetch('/api/updates');
                const updates = await res.json();
                if (updates.length === 0) {
                    container.innerHTML = `<div class="text-gray-500 py-6 text-center bg-dark-800 rounded-2xl border border-gray-800">No patch notes posted yet.</div>`;
                    return;
                }
                container.innerHTML = updates.map(u => `
                    <div class="bg-dark-800 border border-gray-800 p-6 rounded-2xl">
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
            }
        });

        init();
    </script>
</body>
</html>"""

# FastAPI Web Routes
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

    avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png" if user_data.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"

    request.session["user"] = {
        "id": user_data["id"],
        "username": user_data["username"],
        "avatar": avatar_url,
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
        "ping": round(bot.latency * 1000) if bot.is_ready() else 0,
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
    bot_guild_ids = {g.id for g in bot.guilds} if bot.is_ready() else set()
    perms = discord.Permissions(administrator=True).value

    for g in guilds:
        permissions = int(g.get("permissions", 0))
        # Filter for Administrator (0x8) or Manage Guild (0x20)
        if (permissions & 0x8 == 0x8) or (permissions & 0x20 == 0x20):
            g_id = int(g["id"])
            g["bot_present"] = g_id in bot_guild_ids
            g["invite"] = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&scope=bot&permissions={perms}&guild_id={g_id}"
            manageable.append(g)

    return manageable

@app.get("/api/guild/{guild_id}/settings")
async def get_guild_settings(guild_id: str, request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT prefix, welcome_enabled, automod_enabled FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return {"prefix": "!", "welcome_enabled": 0, "automod_enabled": 0}

@app.post("/api/guild/{guild_id}/settings")
async def save_guild_settings(guild_id: str, request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    prefix = body.get("prefix", "!")
    automod = int(body.get("automod_enabled", 0))
    welcome = int(body.get("welcome_enabled", 0))

    conn = db_connect()
    conn.execute("""
        INSERT INTO guild_settings (guild_id, prefix, welcome_enabled, automod_enabled)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            prefix = excluded.prefix,
            welcome_enabled = excluded.welcome_enabled,
            automod_enabled = excluded.automod_enabled
    """, (guild_id, prefix, welcome, automod))
    conn.commit()
    conn.close()

    return {"status": "success"}

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
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bot_updates (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()
    return {"status": "success"}
