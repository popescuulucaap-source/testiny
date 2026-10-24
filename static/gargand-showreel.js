/* Accessible cinematic Gargand walkthrough with the real MP4 and a resilient animated fallback. */
(() => {
  "use strict";
  const film = document.getElementById("ggCinematicFilm");
  if (!film) return;
  const video = film.querySelector("#ggFilmVideo");
  const scenes = Array.from(film.querySelectorAll("[data-film-scene-panel]"));
  const chapters = Array.from(film.querySelectorAll("[data-film-chapter]"));
  const segments = Array.from(film.querySelectorAll("[data-film-segment]"));
  const playButton = film.querySelector("[data-film-play]");
  const pauseButton = film.querySelector("[data-film-pause]");
  const previousButton = film.querySelector("[data-film-previous]");
  const nextButton = film.querySelector("[data-film-next]");
  const position = film.querySelector("[data-film-position]");
  const status = film.querySelector("[data-film-status]");
  if (!scenes.length || !playButton) return;

  const sceneDuration = 5700;
  const titles = ["A new guardian rises", "Security, layer by layer", "Moderation with clarity", "Community stays connected", "Your control room", "Command the chaos"];
  let current = 0;
  let timer = 0;
  let playing = false;
  let videoReady = false;
  const clearTimer = () => { if (timer) window.clearTimeout(timer); timer = 0; };
  const clampIndex = value => Math.max(0, Math.min(scenes.length - 1, value));
  function paint() {
    film.dataset.filmState = playing ? "playing" : (current === scenes.length - 1 && film.dataset.finished === "1" ? "complete" : "paused");
    film.dataset.filmScene = String(current);
    scenes.forEach((scene, index) => {
      const active = index === current;
      scene.classList.toggle("is-active", active);
      scene.setAttribute("aria-hidden", active ? "false" : "true");
    });
    chapters.forEach((button, index) => {
      const active = index === current;
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    const complete = film.dataset.filmState === "complete";
    const sceneSeconds = videoReady && video.duration ? video.duration / scenes.length : sceneDuration / 1000;
    const withinScene = videoReady && video.duration ? (video.currentTime % sceneSeconds) / sceneSeconds : (playing ? 0.52 : 0);
    segments.forEach((button, index) => {
      button.classList.toggle("is-past", index < current || complete);
      button.classList.toggle("is-current", index === current && !complete);
      const fill = button.querySelector("span");
      if (fill) fill.style.width = index < current || complete ? "100%" : (index === current ? String(Math.max(0, Math.min(100, withinScene * 100))) + "%" : "0%");
    });
    if (position) position.textContent = "CHAPTER " + String(current + 1).padStart(2, "0") + " / " + String(scenes.length).padStart(2, "0");
    if (status) status.textContent = playing ? "NOW PLAYING · " + titles[current].toUpperCase() : (complete ? "FILM COMPLETE" : (current > 0 ? "PAUSED · " + titles[current].toUpperCase() : "READY TO PLAY"));
    playButton.innerHTML = '<span class="gg-film-play-symbol" aria-hidden="true">' + (playing ? "Ⅱ" : "▶") + '</span>' + (complete ? "REPLAY THE FILM" : (current > 0 && !playing ? "CONTINUE THE FILM" : "PLAY THE FILM"));
    if (pauseButton) {
      pauseButton.textContent = playing ? "Pause" : "Play";
      pauseButton.setAttribute("aria-label", playing ? "Pause cinematic tour" : "Play cinematic tour");
    }
    if (previousButton) previousButton.disabled = current === 0;
    if (nextButton) nextButton.disabled = current === scenes.length - 1;
  }
  function finish() {
    clearTimer();
    playing = false;
    film.dataset.finished = "1";
    current = scenes.length - 1;
    paint();
  }
  function scheduleFallback() {
    clearTimer();
    if (!playing || videoReady) return;
    timer = window.setTimeout(() => {
      if (current >= scenes.length - 1) { finish(); return; }
      current += 1;
      paint();
      scheduleFallback();
    }, sceneDuration);
  }
  function start() {
    if (film.dataset.finished === "1") current = 0;
    film.dataset.finished = "0";
    playing = true;
    paint();
    if (videoReady && video) {
      if (video.ended || current === 0 && video.currentTime > video.duration - 0.25) video.currentTime = 0;
      const attempt = video.play();
      if (attempt && typeof attempt.catch === "function") attempt.catch(() => {
        videoReady = false;
        film.classList.remove("has-video");
        playing = true;
        paint();
        scheduleFallback();
      });
    } else {
      scheduleFallback();
    }
  }
  function pause() {
    clearTimer();
    playing = false;
    if (videoReady && video && !video.paused) video.pause();
    paint();
  }
  function goTo(index) {
    current = clampIndex(index);
    film.dataset.finished = "0";
    if (videoReady && video && video.duration) {
      video.currentTime = Math.min(video.duration - 0.05, current * (video.duration / scenes.length));
    }
    paint();
    if (playing && !videoReady) scheduleFallback();
  }

  playButton.addEventListener("click", () => playing ? pause() : start());
  if (pauseButton) pauseButton.addEventListener("click", () => playing ? pause() : start());
  if (previousButton) previousButton.addEventListener("click", () => goTo(current - 1));
  if (nextButton) nextButton.addEventListener("click", () => goTo(current + 1));
  chapters.forEach(button => button.addEventListener("click", () => goTo(Number(button.dataset.filmChapter))));
  segments.forEach(button => button.addEventListener("click", () => goTo(Number(button.dataset.filmSegment))));
  film.addEventListener("keydown", event => {
    if (event.altKey || event.ctrlKey || event.metaKey || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
    if (event.key === "ArrowRight") { event.preventDefault(); goTo(current + 1); }
    if (event.key === "ArrowLeft") { event.preventDefault(); goTo(current - 1); }
    if (event.key === "Escape" && playing) pause();
  });

  if (video) {
    video.addEventListener("loadedmetadata", () => {
      if (!Number.isFinite(video.duration) || video.duration <= 0) return;
      videoReady = true;
      film.classList.add("has-video");
      current = clampIndex(Math.floor(video.currentTime / (video.duration / scenes.length)));
      paint();
      if (playing) {
        const attempt = video.play();
        if (attempt && typeof attempt.catch === "function") attempt.catch(() => {
          videoReady = false;
          film.classList.remove("has-video");
          scheduleFallback();
        });
      }
    });
    video.addEventListener("play", () => {
      if (!videoReady) return;
      clearTimer();
      playing = true;
      film.dataset.finished = "0";
      film.classList.add("has-video");
      paint();
    });
    video.addEventListener("pause", () => {
      if (!videoReady || video.ended) return;
      playing = false;
      clearTimer();
      paint();
    });
    video.addEventListener("timeupdate", () => {
      if (!videoReady || !video.duration) return;
      const next = clampIndex(Math.floor(video.currentTime / (video.duration / scenes.length)));
      if (next !== current) current = next;
      paint();
    });
    video.addEventListener("ended", finish);
    video.addEventListener("error", () => {
      videoReady = false;
      film.classList.remove("has-video");
      if (playing) scheduleFallback();
      paint();
    });
  }
  film.dataset.finished = "0";
  paint();
})();
