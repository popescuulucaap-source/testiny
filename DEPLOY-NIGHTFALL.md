# Nightfall setup and deployment

`main.py` contains the existing Discord bot commands and the website bridge. The web app remains a Flask app deployed by Render.

## 1. Set the bot environment on Katabump

At the root of your KataBump server, put `main.py` and upload `requirements-bot.txt` renamed as `requirements.txt` (KataBump auto-installs from a root `requirements.txt`). In the **Startup** tab, select `main.py` as the Python entry point. Keep your existing Discord token variable (`DISCORD_TOKEN`, or `BOT_TOKEN`) and add these lines to the root `.env` file:

```text
BOT_API_SECRET=<a new, long random secret>
BOT_API_PORT=20119
```

Generate a new secret privately with a password manager. Never put it in GitHub or share it in chat. Restart the KataBump server after updating `.env`.

The bot listens on port `20119` for its website API. Only use a KataBump-provided **HTTPS** web endpoint or HTTPS reverse proxy for external access. Do not expose the raw HTTP port to the public internet: the API key would be sent without transport encryption. KataBump's public setup guide does not confirm that a public HTTPS endpoint is available for this bot server; if the panel does not show one, ask KataBump support whether it can provide HTTPS ingress for port `20119` before continuing.

The old API key was embedded in the uploaded script. Treat it as exposed and do not reuse it.

## 2. Connect Render to the bot

In the Render web service's **Environment** page, set:

```text
BOT_API_URL=https://<your-KataBump-HTTPS-endpoint>
BOT_API_SECRET=<the-same-secret-you-set-on-Katabump>
```

Use the exact HTTPS base URL KataBump provides, without adding `/health` to the value. Both services must be online and able to reach each other. The bot API uses `/health`, `/guilds`, and `/guilds/<server-id>/settings`. The website rejects an `http://` API URL so it cannot send the key over an unencrypted connection.

## 3. Keep Discord OAuth pointed at the current Render address

Set `DISCORD_REDIRECT_URI` on Render to the exact URL ending in `/oauth/callback` for the live Nightfall website. Add that same URL to the Discord application's OAuth2 redirect list. The Render service's existing hostname can remain as-is; the displayed product name is Nightfall.

Keep Render's existing `SESSION_SECRET`, Discord OAuth credentials, and database settings. The dashboard needs `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `SESSION_SECRET` to be configured.

## 4. Dashboard prefix behavior

The command prefix starts as `!`, preserving the existing commands. A server administrator can change it in the website dashboard; the bot reads the saved guild prefix for incoming commands. The new prefix is scoped to that server.

