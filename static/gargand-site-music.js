/* Lightweight, user-controlled site-wide music; audio is only fetched after playback is requested. */
(() => {
  "use strict";
  const panel = document.getElementById("ggSiteMusic");
  const button = document.getElementById("ggSiteMusicToggle");
  const status = document.getElementById("ggSiteMusicStatus");
  const power = document.getElementById("ggSiteMusicPower");
  const volume = document.getElementById("ggSiteMusicVolume");
  if (!panel || !button || !status || !volume) return;

  const enabledKey = "gargand-site-music-enabled-v1";
  const volumeKey = "gargand-site-music-volume-v1";
  const audio = new Audio();
  audio.preload = "none";
  audio.loop = true;
  audio.playsInline = true;
  audio.volume = 0.24;

  let enabled = false;
  let failed = false;
  function readSetting(key) {
    try { return window.localStorage.getItem(key); } catch (_) { return null; }
  }
  function writeSetting(key, value) {
    try { window.localStorage.setItem(key, value); } catch (_) {}
  }
  const soundtrackUrl = new URL("/static/gargand-ambient.mp3?v=20261024-music2", window.location.origin).href;
  function useSource(forceReload = false) {
    if (forceReload || audio.src !== soundtrackUrl) {
      audio.src = soundtrackUrl;
      audio.load();
    }
  }
  function paint(message) {
    const on = enabled && !audio.paused && !audio.ended && !failed;
    panel.dataset.state = on ? "playing" : (enabled ? "waiting" : "off");
    button.setAttribute("aria-pressed", on ? "true" : "false");
    button.setAttribute("aria-label", on ? "Pause Gargand ambient soundtrack" : "Play Gargand ambient soundtrack");
    if (power) power.textContent = on ? "Ⅱ" : "▶";
    if (message) status.textContent = message;
    else if (on) status.textContent = "Now playing · Ambient soundtrack";
    else if (failed) status.textContent = "Music could not load · Tap to retry";
    else if (enabled) status.textContent = "Resume soundtrack · Tap to play";
    else status.textContent = "Music off · Tap to play";
  }
  async function startMusic(fromClick) {
    const retryMedia = Boolean(fromClick && (failed || audio.error));
    if (fromClick) {
      enabled = true;
      failed = false;
      writeSetting(enabledKey, "1");
    }
    useSource(retryMedia);
    audio.volume = Number(volume.value) / 100;
    try {
      await audio.play();
      enabled = true;
      failed = false;
      writeSetting(enabledKey, "1");
      paint();
    } catch (error) {
      // Autoplay may be blocked after navigation; a user click should always be allowed to retry.
      enabled = true;
      writeSetting(enabledKey, "1");
      if (error && (error.name === "NotAllowedError" || error.name === "AbortError")) {
        failed = false;
        paint("Playback was blocked · Tap to resume");
      } else {
        failed = true;
        paint("Could not start soundtrack · Tap to retry");
      }
    }
  }
  function stopMusic() {
    enabled = false;
    audio.pause();
    writeSetting(enabledKey, "0");
    paint();
  }

  const savedVolume = Number(readSetting(volumeKey));
  if (Number.isFinite(savedVolume) && savedVolume >= 0 && savedVolume <= 60) volume.value = String(savedVolume);
  audio.volume = Number(volume.value) / 100;
  volume.addEventListener("input", () => {
    audio.volume = Number(volume.value) / 100;
    writeSetting(volumeKey, volume.value);
  });
  button.addEventListener("click", () => {
    if (enabled && !audio.paused) stopMusic();
    else startMusic(true);
  });
  audio.addEventListener("playing", () => { failed = false; paint(); });
  audio.addEventListener("pause", () => { if (!enabled) paint(); });
  audio.addEventListener("error", () => {
    failed = true;
    const code = audio.error && audio.error.code;
    const message = code === 2 ? "Network error loading soundtrack · Tap to retry"
      : code === 3 ? "Soundtrack audio could not be decoded · Tap to retry"
      : code === 4 ? "Soundtrack file is unavailable · Tap to retry"
      : "Could not load soundtrack · Tap to retry";
    paint(message);
  });

  // Remember the music choice across page navigation without trying to bypass autoplay rules.
  if (readSetting(enabledKey) === "1") startMusic(false);
  else paint();
})();
