            cur.execute("CREATE TABLE IF NOT EXISTS support_tickets (id BIGSERIAL PRIMARY KEY, token TEXT UNIQUE NOT NULL, name TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS support_messages (id BIGSERIAL PRIMARY KEY, ticket_id BIGINT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE, sender TEXT NOT NULL, message TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS social_videos (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, username TEXT NOT NULL, avatar_url TEXT NOT NULL, video_url TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', strikes INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS social_follows (follower_id TEXT NOT NULL, following_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (follower_id, following_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS social_reports (id BIGSERIAL PRIMARY KEY, video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, reporter_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS site_profiles (discord_id TEXT PRIMARY KEY, username TEXT NOT NULL, avatar_url TEXT NOT NULL DEFAULT '', xp INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS site_xp_events (discord_id TEXT NOT NULL, action TEXT NOT NULL, last_awarded TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (discord_id, action))")
            cur.execute("CREATE TABLE IF NOT EXISTS site_notifications (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, read BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_scores (id BIGSERIAL PRIMARY KEY, discord_id TEXT NOT NULL, username TEXT NOT NULL, game TEXT NOT NULL, score INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_challenges (discord_id TEXT PRIMARY KEY, started_at DOUBLE PRECISION NOT NULL, hits INTEGER NOT NULL DEFAULT 0, completed BOOLEAN NOT NULL DEFAULT FALSE)")
            cur.execute("CREATE TABLE IF NOT EXISTS arcade_rewards (discord_id TEXT PRIMARY KEY, code TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), redeemed_at TIMESTAMPTZ NULL, redeemed_by TEXT NULL)")
            # Safe, backwards-compatible migration. Older installs used code_hash.
            # Keep that legacy column nullable instead of dropping it during startup;
            # this avoids breaking existing rows/constraints while allowing new rows
            # to use the account-bound code column.
            columns = {row[0] for row in cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'arcade_rewards'"
            ).fetchall()}
            if "code" not in columns:
                cur.execute("ALTER TABLE arcade_rewards ADD COLUMN code TEXT")
            if "code_hash" in columns:
                cur.execute("ALTER TABLE arcade_rewards ALTER COLUMN code_hash DROP NOT NULL")
            cur.execute("UPDATE arcade_rewards SET code=%s WHERE code IS NULL OR code=''", ("ducky-squad",))
            cur.execute("ALTER TABLE arcade_rewards ALTER COLUMN code SET NOT NULL")
            cur.execute("CREATE TABLE IF NOT EXISTS site_settings (discord_id TEXT PRIMARY KEY, bio TEXT NOT NULL DEFAULT '', theme TEXT NOT NULL DEFAULT 'default', title TEXT NOT NULL DEFAULT '')")
            cur.execute("CREATE TABLE IF NOT EXISTS site_achievements (discord_id TEXT NOT NULL, achievement TEXT NOT NULL, unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (discord_id, achievement))")
            cur.execute("CREATE TABLE IF NOT EXISTS site_reputation (discord_id TEXT PRIMARY KEY, score INTEGER NOT NULL DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS social_likes (video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (video_id, discord_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS social_comments (id BIGSERIAL PRIMARY KEY, video_id BIGINT NOT NULL REFERENCES social_videos(id) ON DELETE CASCADE, discord_id TEXT NOT NULL, username TEXT NOT NULL, avatar_url TEXT NOT NULL DEFAULT '', body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'approved', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        conn.commit()

def load_announcements():
    if not DATABASE_URL:
        return session.get("announcements", [])
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, body, date, kind FROM announcements ORDER BY id DESC")
            return [{"id":r[0],"title":r[1],"body":r[2],"date":r[3],"kind":r[4] if len(r) > 4 else "website"} for r in cur.fetchall()]

def save_announcement(title, body, kind="website"):
    date=__import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")