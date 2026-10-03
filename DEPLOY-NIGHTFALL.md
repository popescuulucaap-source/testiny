# Nightfall setup and deployment

`main.py` preserves the existing Discord bot commands and uses an outbound HTTPS bridge to the Flask website on Render. KataBump does not need an inbound port, public API endpoint, tunnel, or reverse proxy.

## KataBump bot

Upload the updated `main.py` to the server root. Upload `requirements-bot.txt` as `requirements.txt` so KataBump installs `requests` along with the bot dependencies. In **Startup**, keep `main.py` as the Python entry point.

Keep the existing Discord token in KataBump's `.env` and set:

```text
NIGHTFALL_WEBSITE_URL=https://testiny-7wuu.onrender.com
NIGHTFALL_BRIDGE_SECRET=<same long random secret as Render>
```

To enable Nightfall's AI studio commands, add `OPENAI_API_KEY` as a private KataBump environment variable and restart the bot. This enables `!ask`, `!story`, `!roast`, `!compliment`, `!riddle`, `!poem`, `!joke`, `!caption`, `!namegen` / `!names`, `!quiz`, and `!aiimage` / `!aiart`. Requests use OpenAI's API and may incur usage charges; the commands stay unavailable until the key is configured. The text model defaults to `gpt-5.4-mini`; optionally set `OPENAI_TEXT_MODEL` to another API model available to your account. Never put the key in GitHub or share it in chat.

The bridge uses HTTPS from KataBump to Render. The bot checks in every 10 seconds, reports its guild list and settings, and pulls dashboard changes. Do not add an inbound listener or expose port `20119` for the website bridge.

## Render website

In the Render web service's **Environment** settings, set `NIGHTFALL_BRIDGE_SECRET` to the exact same random value used in the bot's `.env`. Generate the value privately with a password manager. Never put the secret in GitHub or send it in chat. Save the environment change; Render will restart the site.

Keep Render's existing `SESSION_SECRET`, Discord OAuth credentials, and database settings. `DISCORD_REDIRECT_URI` must end in `/oauth/callback` for the live website and that same URL must be listed in the Discord application's OAuth2 redirect list.

## Dashboard behavior

The command prefix starts as `!`, preserving the existing commands. An administrator can change the prefix or logs channel from the website dashboard. Settings and setup refresh actions are queued by the website and picked up on the bot's next HTTPS check-in. The dashboard cache is refreshed every 10 seconds while the bot is online.

## Discord profile copy

The `!about` command and website show the `1.0v LAUNCH` label. To use the same copy in Discord's Developer Portal profile, paste:

> 🌙 Nightfall is your all-in-one Discord guardian: smooth moderation, smart server safety, tickets, invites, giveaways, games, and creative tools. Set up your server with !setup, then let the night run smoother. ✨
