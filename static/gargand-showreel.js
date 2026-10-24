/* Continuous, auto-playing Gargand showcase with cross-faded chapters and no video selector UI. */
(() => {
  "use strict";
  const film = document.getElementById("ggCinematicFilm");
  if (!film) return;
  const video = film.querySelector("#ggFilmVideo");
  const scenes = Array.from(film.querySelectorAll("[data-film-scene-panel]"));
  const soundButton = film.querySelector("[data-film-sound]");
  if (!video || !scenes.length) return;

  const reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const crossfadeLead = 1.05;
  const fallbackDelay = 5700;
  let current = -1;
  let videoReady = false;
  let inView = false;
  let suspended = false;
  let fallbackTimer = 0;

  function activateScene(index) {
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
    if (!videoReady || !Number.isFinite(video.duration) || video.duration <= 0) return;
    const segmentLength = video.duration / scenes.length;
    // Start the text dissolve alongside the film's background crossfade, not after the cut.
    const time = (video.currentTime + Math.min(crossfadeLead, segmentLength * 0.18)) % video.duration;
    activateScene(Math.floor(time / segmentLength));
  }

  function paintSoundButton() {
    if (!soundButton) return;
    const soundOn = !video.muted;
    soundButton.textContent = soundOn ? "♫ SOUND ON" : "♫ SOUND OFF";
    soundButton.setAttribute("aria-pressed", soundOn ? "true" : "false");
    soundButton.setAttribute("aria-label", soundOn ? "Mute cinematic soundtrack" : "Enable cinematic soundtrack");
    soundButton.classList.toggle("is-on", soundOn);
  }

  function clearFallback() {
    if (fallbackTimer) window.clearTimeout(fallbackTimer);
    fallbackTimer = 0;
  }

  function scheduleFallback() {
    clearFallback();
    if (reduceMotion || videoReady || !inView || suspended || document.hidden) return;
    fallbackTimer = window.setTimeout(() => {
      activateScene(current < 0 ? 0 : current + 1);
      scheduleFallback();
    }, fallbackDelay);
  }

  function startFilm() {
    if (reduceMotion || !inView || suspended || document.hidden) return;
    const attempt = video.play();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => {
        film.classList.remove("has-video");
        scheduleFallback();
      });
    }
  }

  video.muted = true;
  video.defaultMuted = true;
  video.loop = true;
  video.playsInline = true;
  film.dataset.filmState = "continuous";
  activateScene(0);
  paintSoundButton();

  video.addEventListener("loadedmetadata", () => {
    if (!Number.isFinite(video.duration) || video.duration <= 0) return;
    videoReady = true;
    clearFallback();
    syncSceneToFilm();
    if (inView && !reduceMotion && !suspended) startFilm();
  });
  video.addEventListener("loadeddata", () => {
    if (inView && !reduceMotion && !suspended) startFilm();
  });
  video.addEventListener("play", () => {
    film.classList.add("has-video");
    film.dataset.filmState = "continuous";
    clearFallback();
    syncSceneToFilm();
  });
  video.addEventListener("timeupdate", syncSceneToFilm);
  video.addEventListener("error", () => {
    videoReady = false;
    film.classList.remove("has-video");
    scheduleFallback();
  });

  if (soundButton) {
    soundButton.addEventListener("click", () => {
      video.muted = !video.muted;
      video.volume = 0.72;
      paintSoundButton();
      if (!video.muted) startFilm();
    });
  }

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.target !== film) return;
        inView = entry.isIntersecting && entry.intersectionRatio >= 0.08;
        if (inView) {
          suspended = false;
          if (!reduceMotion) startFilm();
        } else {
          suspended = true;
          clearFallback();
          if (!video.paused) video.pause();
        }
      });
    }, { threshold: [0, 0.08, 0.2], rootMargin: "80px 0px 80px 0px" });
    observer.observe(film);
  } else {
    inView = true;
    if (!reduceMotion) startFilm();
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      suspended = true;
      clearFallback();
      if (!video.paused) video.pause();
    } else {
      suspended = false;
      if (inView && !reduceMotion) startFilm();
    }
  });
})();
