/* Silent ambient backplates with cross-faded swaps for every Gargand tab. */
(() => {
  "use strict";
  const reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const saveData = !!(navigator.connection && navigator.connection.saveData);
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const scenes = {
    "/": "home", "/commands": "commands", "/security": "security", "/verification": "verification",
    "/support": "support", "/announcements": "announcements", "/servers": "dashboard", "/dashboard": "dashboard",
    "/admin": "dashboard", "/admin/panel": "dashboard", "/admin/audit": "dashboard", "/admin/community": "community", "/admin/support": "support",
    "/guild/analytics": "dashboard", "/guild/moderation": "security", "/socials": "community", "/community": "community", "/profile": "community",
    "/passport": "community", "/nightfall-passport": "community", "/achievements": "community", "/leaderboards": "community", "/daily": "community",
    "/notifications": "announcements", "/suggestions": "community", "/suggestions/list": "community",
    "/guidelines": "security", "/terms": "verification", "/login": "home", "/premium": "dashboard", "/redeem": "dashboard", "/secrets": "security"
  };
  let kind = scenes[path];
  if (!kind && /^\/dashboard\/\d+(?:\/|$)/.test(path)) {
    kind = /analytics/.test(path) ? "dashboard" : (/moderation/.test(path) ? "security" : "dashboard");
  }
  if (!kind || reduced || saveData) return;

  const targets = path === "/"
    ? [document.querySelector(".gg-hero")]
    : [
        document.querySelector("#main-content > .page-head"),
        document.querySelector("#main-content > .dashboard-header"),
        document.querySelector("#main-content > .server-header"),
        document.querySelector("#main-content > .dashboard-head")
      ].filter(Boolean);

  const videoSource = value => "/static/gargand-scenes/" + value + ".mp4?v=20261024-smooth5";

  targets.filter(Boolean).forEach((target, slot) => {
    if (target.querySelector(":scope > .gg-page-scene")) return;
    target.classList.add("gg-has-page-scene");
    const wrapper = document.createElement("div");
    wrapper.className = "gg-page-scene";
    wrapper.setAttribute("aria-hidden", "true");
    wrapper.dataset.sceneKind = kind;

    const video = document.createElement("video");
    video.className = "gg-page-scene-video";
    video.muted = true;
    video.defaultMuted = true;
    video.autoplay = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = slot === 0 ? "metadata" : "none";
    video.setAttribute("muted", "");
    video.setAttribute("playsinline", "");
    video.setAttribute("aria-hidden", "true");
    video.disablePictureInPicture = true;
    video.src = videoSource(kind);
    video.dataset.sceneSource = videoSource(kind);
    video.addEventListener("loadeddata", () => video.classList.add("is-visible"), { once: true });
    video.addEventListener("play", () => video.classList.add("is-visible"));
    const grain = document.createElement("span");
    grain.className = "gg-page-scene-grain";
    wrapper.append(video, grain);
    target.prepend(wrapper);

    const play = video.play();
    if (play && typeof play.catch === "function") play.catch(() => wrapper.classList.add("is-static"));
    const visibility = "IntersectionObserver" in window ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          if (video.paused) video.play().catch(() => {});
        } else if (!video.paused) {
          video.pause();
        }
      });
    }, { threshold: 0.01, rootMargin: "100px 0px" }) : null;
    if (visibility) visibility.observe(target);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        if (!video.paused) video.pause();
      } else if (!reduced && !saveData && target.getBoundingClientRect().bottom > 0 && target.getBoundingClientRect().top < window.innerHeight) {
        video.play().catch(() => {});
      }
    });
  });

  // Dashboard/header tabs get a second video layer so new ambience can load underneath the current one.
  const scene = document.querySelector("#main-content .gg-page-scene") || document.querySelector(".gg-page-scene");
  if (!scene) return;
  const container = scene;
  let front = scene.querySelector("video");
  if (!front) return;
  const back = document.createElement("video");
  back.className = "gg-page-scene-video";
  back.muted = true;
  back.defaultMuted = true;
  back.loop = true;
  back.playsInline = true;
  back.preload = "none";
  back.setAttribute("muted", "");
  back.setAttribute("playsinline", "");
  back.setAttribute("aria-hidden", "true");
  back.disablePictureInPicture = true;
  container.insertBefore(back, container.querySelector(".gg-page-scene-grain"));

  let selectedKind = container.dataset.sceneKind || kind;
  let requestNumber = 0;
  const sceneForLabel = label => {
    const value = (label || "").toLowerCase();
    if (/security|moderat|audit|incident/.test(value)) return "security";
    if (/command|bot|setup|music/.test(value)) return "commands";
    if (/support|ticket|community|member|social|profile/.test(value)) return "community";
    if (/notification|announcement|release|activity/.test(value)) return "announcements";
    if (/verif|lock|appeal|access/.test(value)) return "verification";
    return "dashboard";
  };

  function crossFadeTo(nextKind) {
    if (!nextKind || nextKind === selectedKind) return;
    const source = videoSource(nextKind);
    if (front.dataset.sceneSource === source) return;
    const request = ++requestNumber;
    back.pause();
    back.classList.remove("is-visible");
    back.removeAttribute("src");
    back.load();
    back.src = source;
    back.dataset.sceneSource = source;

    const showNewScene = () => {
      back.removeEventListener("loadeddata", showNewScene);
      if (request !== requestNumber) return;
      back.play().catch(() => {});
      back.classList.add("is-visible");
      front.classList.remove("is-visible");
      const oldFront = front;
      front = back;
      oldFront.dataset.sceneSource = oldFront.dataset.sceneSource || "";
      // Reuse the faded-out layer on the next tab change, after its opacity transition completes.
      back = oldFront;
      selectedKind = nextKind;
      container.dataset.sceneKind = nextKind;
      window.setTimeout(() => {
        if (!oldFront.classList.contains("is-visible")) oldFront.pause();
      }, 1450);
    };
    back.addEventListener("loadeddata", showNewScene);
    back.addEventListener("error", () => {
      back.removeEventListener("loadeddata", showNewScene);
    }, { once: true });
    back.load();
  }

  document.querySelectorAll('[role="tab"],[data-tab],.dashboard-tab,.tab-button').forEach(button => {
    button.addEventListener("click", () => crossFadeTo(sceneForLabel(button.textContent || button.getAttribute("aria-label"))));
  });
})();
