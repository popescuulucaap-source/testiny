(() => {
  "use strict";
  const intro = document.getElementById("ggCinematicIntro");
  if (!intro) return;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let seen = false;
  try { seen = sessionStorage.getItem("gargand-intro-seen") === "1"; } catch (_) {}
  const close = () => {
    if (intro.dataset.closed === "1") return;
    intro.dataset.closed = "1";
    try { sessionStorage.setItem("gargand-intro-seen", "1"); } catch (_) {}
    intro.classList.add("is-leaving");
    document.body.classList.add("gg-intro-complete");
    window.setTimeout(() => { intro.hidden = true; }, 780);
  };
  intro.querySelectorAll("[data-intro-dismiss]").forEach(button => button.addEventListener("click", close));
  intro.addEventListener("keydown", event => { if (event.key === "Escape" || event.key === "Enter") { event.preventDefault(); close(); } });
  if (reduced || seen) {
    intro.hidden = true;
    document.body.classList.add("gg-intro-complete");
    return;
  }
  const timer = window.setTimeout(close, 4400);
  intro.querySelectorAll("[data-intro-dismiss]").forEach(button => button.addEventListener("click", () => window.clearTimeout(timer), {once:true}));
  const enter = intro.querySelector(".gg-intro-enter");
  if (enter) enter.focus({preventScroll:true});
})();