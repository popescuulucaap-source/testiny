/* One continuous background film shared by all Gargand pages. */
(() => {
  "use strict";

  const video = document.getElementById("ggFilmVideo");
  if (!video) return;

  const film = document.getElementById("ggCinematicFilm");
  const scenes = film ? Array.from(film.querySelectorAll("[data-film-scene-panel]")) : [];
  const soundButton = film ? film.querySelector("[data-film-sound]") : null;
  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const fallbackDelay = 5700;
  let current = -1;
  let fallbackTimer = 0;

  function activateScene(index) {
    if (!film || !scenes.length) return;
    index = (index + scenes.length) % scenes.length;
    if (index === current) return;
    current = index;
    film.dataset.filmScene = String(index);
    scenes.forEach((scene, sceneIndex) => {
      const active = sceneIndex === index;
      scene.classList.toggle("is-active", active);
      scene.setAttribute("aria-hidden", active ? "false" : "true");
    });
  }

  function syncSceneToFilm() {
    if (!film || !scenes.length || !Number.isFinite(video.duration) || video.duration <= 0) return;
    const segmentLength = video.duration / scenes.length;
    const lead = Math.min(1.05, segmentLength * 0.18);
    const time = (video.currentTime + lead) % video.duration;
    activateScene(Math.floor(time / segmentLength));
  }

  function clearFallback() {
    if (fallbackTimer) window.clearTimeout(fallbackTimer);
    fallbackTimer = 0;
  }

  function scheduleFallback() {
    clearFallback();
    if (!film || !scenes.length || reduceMotion || document.hidden) return;
    fallbackTimer = window.setTimeout(() => {
      activateScene(current < 0 ? 0 : current + 1);
      scheduleFallback();
    }, fallbackDelay);
  }

  function paintSoundButton() {
    if (!soundButton) return;
    const soundOn = !video.muted;
    soundButton.textContent = soundOn ? "♫ SOUND ON" : "♫ SOUND OFF";
    soundButton.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundButton.setAttribute("aria-label", soundOn ? "Mute cinematic soundtrack" : "Enable cinematic soundtrack");
    soundButton.classList.toggle("is-on", soundOn);
  }

  function startBackground() {
    if (reduceMotion || document.hidden) return;
    const attempt = video.play();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => {
        scheduleFallback();
      });
    }
  }

  video.muted = true;
  video.defaultMuted = true;
  video.loop = true;
  video.playsInline = true;
  if (film) film.dataset.filmState = "continuous";
  activateScene(0);
  paintSoundButton();

  video.addEventListener("loadedmetadata", syncSceneToFilm);
  if (video.readyState >= HTMLMediaElement.HAVE_METADATA) syncSceneToFilm();
  video.addEventListener("timeupdate", syncSceneToFilm);
  video.addEventListener("play", () => {
    clearFallback();
    document.documentElement.classList.add("gargand-background-video-playing");
    if (film) film.dataset.filmState = "continuous";
    syncSceneToFilm();
  });
  video.addEventListener("error", scheduleFallback);

  if (soundButton) {
    soundButton.addEventListener("click", () => {
      video.muted = !video.muted;
      video.volume = 0.72;
      paintSoundButton();
      startBackground();
    });
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearFallback();
      if (!video.paused) video.pause();
    } else {
      startBackground();
      if (video.paused) scheduleFallback();
    }
  });

  window.addEventListener("pageshow", startBackground);
  startBackground();
})();
