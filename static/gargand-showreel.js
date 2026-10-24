/* Accessible, chapter-based cinematic walkthrough for the Gargand homepage. */
(() => {
  "use strict";
  const film = document.getElementById("ggCinematicFilm");
  if (!film) return;
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

  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const sceneDuration = reducedMotion ? 7800 : 5700;
  let current = 0;
  let timer = 0;
  let playing = false;

  const titles = ["A new guardian rises", "Security, layer by layer", "Moderation with clarity", "Community stays connected", "Your control room", "Command the chaos"];
  const clearTimer = () => { if (timer) window.clearTimeout(timer); timer = 0; };
  function paint() {
    film.dataset.filmScene = String(current);
    film.dataset.filmState = playing ? "playing" : (current === scenes.length - 1 && film.dataset.finished === "1" ? "complete" : "paused");
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
    segments.forEach((button, index) => {
      button.classList.toggle("is-past", index < current || film.dataset.filmState === "complete");
      button.classList.toggle("is-current", index === current && film.dataset.filmState !== "complete");
      const fill = button.querySelector("span");
      if (fill) fill.style.width = index < current || film.dataset.filmState === "complete" ? "100%" : (index === current && playing ? "52%" : "0%");
    });
    if (position) position.textContent = "CHAPTER " + String(current + 1).padStart(2, "0") + " / " + String(scenes.length).padStart(2, "0");
    if (status) status.textContent = playing ? "NOW PLAYING · " + titles[current].toUpperCase() : (film.dataset.filmState === "complete" ? "FILM COMPLETE" : (film.dataset.filmState === "paused" && current > 0 ? "PAUSED · " + titles[current].toUpperCase() : "READY TO PLAY"));
    playButton.innerHTML = '<span class="gg-film-play-symbol" aria-hidden="true">' + (playing ? "Ⅱ" : "▶") + '</span>' + (film.dataset.filmState === "complete" ? "REPLAY THE FILM" : (current > 0 && !playing ? "CONTINUE THE FILM" : "PLAY THE FILM"));
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
    paint();
  }
  function schedule() {
    clearTimer();
    if (!playing) return;
    timer = window.setTimeout(() => {
      if (current >= scenes.length - 1) { finish(); return; }
      current += 1;
      paint();
      schedule();
    }, sceneDuration);
  }
  function start() {
    if (film.dataset.filmState === "complete" || film.dataset.finished === "1") current = 0;
    film.dataset.finished = "0";
    playing = true;
    paint();
    schedule();
  }
  function pause() {
    clearTimer();
    playing = false;
    paint();
  }
  function goTo(index) {
    current = Math.max(0, Math.min(scenes.length - 1, index));
    film.dataset.finished = "0";
    paint();
    if (playing) schedule();
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
  film.dataset.finished = "0";
  paint();
})();
