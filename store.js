"use strict";
// Tiny key/value store.
// - With DATABASE_URL set: saved in Postgres (survives Render restarts).
// - Without it: saved in data.json (on Render's free plan this file is wiped on every restart).
const fs = require("fs");
const path = require("path");

const FILE = process.env.DATA_FILE || path.join(__dirname, "data.json");
const persistent = Boolean(process.env.DATABASE_URL);
let pool = null;
let cache = null;

if (persistent) {
  const { Pool } = require("pg");
  pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.PGSSL === "disable" ? false : { rejectUnauthorized: false },
    max: 3,
  });
}

async function init() {
  if (pool) {
    await pool.query("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value JSONB NOT NULL)");
    const { rows } = await pool.query("SELECT key, value FROM kv");
    cache = Object.fromEntries(rows.map((r) => [r.key, r.value]));
  } else {
    try {
      cache = JSON.parse(fs.readFileSync(FILE, "utf8"));
    } catch {
      cache = {};
    }
  }
}

async function get(key, fallback) {
  return cache && key in cache ? cache[key] : fallback;
}

async function set(key, value) {
  cache[key] = value;
  if (pool) {
    await pool.query(
      "INSERT INTO kv (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
      [key, JSON.stringify(value)]
    );
  } else {
    fs.writeFileSync(FILE, JSON.stringify(cache));
  }
}

module.exports = { init, get, set, persistent };
