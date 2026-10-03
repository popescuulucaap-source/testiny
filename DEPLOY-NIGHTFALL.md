# Nightfall setup and deployment

`main.py` contains the existing Discord bot commands and the website bridge. The web app remains a Flask app deployed by Render.

## 1. Set the bot environment on Katabump

Use `main.py` as the startup file and install `requirements-bot.txt`. Keep the existing Discord bot token variable (`DISCORD_TOKEN`, or `BOT_TOKEN`) and add:

```text
BOT_API_SECRET=<a new, long random secret>
BOT_API_PORT=20119
```

Generate a secret privately, for example with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never put the generated value in GitHub, a Discord message, or this file. Configure Katabump to expose TCP port `20119` publicly for the bot's HTTP API. The bot still listens on all interfaces, as required by a hosted service.

The old API key was embedded in the uploaded script. Treat it as exposed and do not reuse it.

## 2. Connect Render to the bot

In the Render web service environment, set:

```text
BOT_API_URL=https://<your-public-Katabump-host>:20119
BOT_API_SECRET=<the-same-secret-you-set-on-Katabump>
```

If Katabump gives you a public URL that already includes a port or path, use its exact public API base URL. Both services must be online and able to reach each other. The bot API uses `/health`, `/guilds`, and `/guilds/<server-id>/settings`.

## 3. Keep Discord OAuth pointed at the current Render address

Set `DISCORD_REDIRECT_URI` on Render to the exact URL ending in `/oauth/callback` for the live Nightfall website. Add that same URL to the Discord application's OAuth2 redirect list. The Render service's existing hostname can remain as-is; the displayed product name is Nightfall.

Keep Render's existing `SESSION_SECRET`, Discord OAuth credentials, and database settings. The dashboard needs `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `SESSION_SECRET` to be configured.

## 4. Dashboard prefix behavior

The command prefix starts as `!`, preserving the existing commands. A server administrator can change it in the website dashboard; the bot reads the saved guild prefix for incoming commands. The new prefix is scoped to that server.

