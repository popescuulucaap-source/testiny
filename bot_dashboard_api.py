"""
Testiny Bot -> Dashboard bridge.

This file is an integration template for your existing discord.py bot.
Run it in the SAME Python process as the bot, or adapt the routes to your
existing bot architecture.

Install aiohttp if you use this file:
    pip install aiohttp

The dashboard sends X-Testiny-API-Key. Keep the same secret in Render.

Important:
- This bridge intentionally does NOT expose a Discord bot token.
- Add your own permission checks for every destructive action.
- The settings shown here are a simple starting point; connect them to the
  actual setup/config storage used by your bot.
"""

import os
from aiohttp import web

DASHBOARD_API_SECRET = os.getenv("BOT_API_SECRET", "")


def api_auth(request):
    return bool(DASHBOARD_API_SECRET) and request.headers.get("X-Testiny-API-Key") == DASHBOARD_API_SECRET


def create_dashboard_api(bot, settings_store):
    routes = web.RouteTableDef()

    @routes.get("/health")
    async def health(request):
        return web.json_response({"ok": True, "service": "Testiny Bot API"})

    @routes.get("/guilds")
    async def guilds(request):
        if not api_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        return web.json_response({
            "guilds": [{"id": str(g.id), "name": g.name, "member_count": g.member_count} for g in bot.guilds]
        })

    @routes.get("/guilds/{guild_id}/settings")
    async def get_settings(request):
        if not api_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        guild_id = int(request.match_info["guild_id"])
        if not bot.get_guild(guild_id):
            return web.json_response({"error": "Bot is not in this server."}, status=404)
        return web.json_response(settings_store.get(str(guild_id), {"prefix": "!"}))

    @routes.post("/guilds/{guild_id}/settings")
    async def save_settings(request):
        if not api_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        guild_id = int(request.match_info["guild_id"])
        guild = bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Bot is not in this server."}, status=404)

        payload = await request.json()
        current = settings_store.setdefault(str(guild_id), {"prefix": "!"})

        # TODO: connect each field to your real setup/database.
        # This example keeps dashboard state in the provided settings_store.
        if "prefix" in payload:
            prefix = str(payload["prefix"]).strip()
            if 1 <= len(prefix) <= 5:
                current["prefix"] = prefix

        for key in ("logs_channel", "section", "features"):
            if key in payload:
                current[key] = payload[key]

        return web.json_response({"ok": True, "settings": current})

    @routes.post("/guilds/{guild_id}/actions")
    async def action(request):
        if not api_auth(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        guild_id = int(request.match_info["guild_id"])
        guild = bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Bot is not in this server."}, status=404)

        payload = await request.json()
        action_name = payload.get("action")

        # Add carefully permission-checked bot actions here.
        # Example names:
        # "sync_setup", "create_ticket_panel", "lock_channel", "send_announcement"
        return web.json_response({
            "ok": True,
            "guild_id": str(guild_id),
            "action": action_name,
            "message": "Action received. Connect this action to your bot command/service layer."
        })

    app = web.Application()
    app.add_routes(routes)
    return app
