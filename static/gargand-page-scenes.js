/* Lazy, low-power-aware page ambience with optional crossfades inside dashboards. */
(() => {
  "use strict";
  const reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const saveData = !!(connection && connection.saveData);
  const cores = Number(navigator.hardwareConcurrency || 0);
  const memory = Number(navigator.deviceMemory || 0);
  const lowPower = (cores > 0 && cores <= 4) || (memory > 0 && memory <= 4);
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const sceneMap = {
    "/": "home", "/commands": "commands", "/security": "security", "/verification": "verification",
    "/support": "support", "/announcements": "announcements", "/servers": "dashboard", "/dashboard": "dashboard",
    "/admin": "dashboard", "/admin/panel": "dashboard", "/admin/audit": "dashboard", "/admin/community": "community", "/admin/support": "support",
    "/guild/analytics": "dashboard", "/guild/moderation": "security", "/socials": "community", "/community": "community", "/profile": "community",
    "/passport": "community", "/nightfall-passport": "community", "/achievements": "community", "/leaderboards": "community", "/daily": "community",
    "/notifications": "announcements", "/suggestions": "community", "/suggestions/list": "community",
    "/guidelines": "security", "/terms": "verification", "/login": "home", "/premium": "dashboard", "/redeem": "dashboard", "/secrets": "security"
  };
  let initialKind = sceneMap[path];
  if (!initialKind && /^\/dashboard\/\d+(?:\/|$)/.test(path)) {
    initialKind = /analytics/.test(path) ? "dashboard" : (/moderation/.test(path) ? "security" : "dashboard");
  }
  // Static glow CSS remains the fallback; avoid decoding video on reduced-motion, data-saver and lower-powered devices.
  if (!initialKind || reduced || saveData || lowPower) return;

  const targets = path === "/"
    ? [document.querySelector(".gg-hero")]
    : [
        document.querySelector("#main-content > .page-head"),
        document.querySelector("#main-content > .dashboard-header"),
        document.querySelector("#main-content > .server-header"),
        document.querySelector("#main-content > .dashboard-head")
      ].filter(Boolean);
  const controllers = [];
  const videoSource = name => "/static/gargand-scenes/" + name + ".mp4?v=20261024-performance1";

  function createVideo() {
    const video = document.createElement("video");
    video.className = "gg-page-scene-video";
    video.muted = true;
    video.defaultMuted = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = "none";
    video.setAttribute("muted", "");
    video.setAttribute("playsinline", "");
    video.setAttribute("aria-hidden", "true");
    video.disablePictureInPicture = true;
    video.addEventListener("loadeddata", () => video.classList.add("is-visible"), { once: true });
    video.addEventListener("play", () => video.classList.add("is-visible"));
    return video;
  }

  function loadAndPlay(video, name) {
    const source = videoSource(name);
    if (video.dataset.sceneSource !== source) {
      video.dataset.sceneSource = source;
      video.removeAttribute("src");
      video.src = source;
      video.load();
    }
    const attempt = video.play();
    if (attempt && typeof attempt.catch === "function") {
      attempt.catch(() => video.closest(".gg-page-scene")?.classList.add("is-static"));
    }
  }

  targets.filter(Boolean).forEach(target => {
    if (target.querySelector(":scope > .gg-page-scene")) return;
    target.classList.add("gg-has-page-scene");
    const wrapper = document.createElement("div");
    wrapper.className = "gg-page-scene";
    wrapper.setAttribute("aria-hidden", "true");
    wrapper.dataset.sceneKind = initialKind;
    const video = createVideo();
    const grain = document.createElement("span");
    grain.className = "gg-page-scene-grain";
    wrapper.append(video, grain);
    target.prepend(wrapper);

    const controller = {
      target, wrapper, front: video, back: null, kind: initialKind,
      visible: false, request: 0,
      start() {
        this.visible = true;
        loadAndPlay(this.front, this.kind);
      },
      stop() {
        this.visible = false;
        [this.front, this.back].filter(Boolean).forEach(item => {
          if (!item.paused) item.pause();
        });
      },
      crossFade(nextKind) {
        if (!nextKind || nextKind === this.kind) return;
        this.kind = nextKind;
        wrapper.dataset.sceneKind = nextKind;
        if (!this.visible) return;
        if (!this.back) {
          this.back = createVideo();
          wrapper.insertBefore(this.back, grain);
        }
        const incoming = this.back;
        const request = ++this.request;
        incoming.pause();
        incoming.classList.remove("is-visible");
        incoming.removeAttribute("src");
        incoming.dataset.sceneSource = "";
        const onReady = () => {
          incoming.removeEventListener("loadeddata", onReady);
          if (request !== this.request || !this.visible) return;
          const attempt = incoming.play();
          if (attempt && typeof attempt.catch === "function") attempt.catch(() => {});
          incoming.classList.add("is-visible");
          const outgoing = this.front;
          outgoing.classList.remove("is-visible");
          this.front = incoming;
          this.back = outgoing;
          window.setTimeout(() => {
            if (outgoing !== this.front && !outgoing.classList.contains("is-visible")) outgoing.pause();
          }, 1450);
        };
        incoming.addEventListener("loadeddata", onReady);
        loadAndPlay(incoming, nextKind);
      }
    };
    controllers.push(controller);

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.target !== target) return;
          if (entry.isIntersecting) controller.start();
          else controller.stop();
        });
      }, { threshold: 0.01, rootMargin: "100px 0px" });
      observer.observe(target);
    } else {
      controller.start();
    }
  });

  const dashboardPath = /^\/(dashboard|servers|admin)(\/|$)/.test(path);
  if (dashboardPath && controllers.length) {
    const tabs = Array.from(document.querySelectorAll('#main-content [role="tab"], #main-content [data-tab], #main-content .dashboard-tab, #main-content .tab-button'));
    const sceneForLabel = label => {
      const value = (label || "").toLowerCase();
      if (/security|moderat|audit|incident/.test(value)) return "security";
      if (/command|bot|setup|music/.test(value)) return "commands";
      if (/support|ticket|community|member|social|profile/.test(value)) return "community";
      if (/notification|announcement|release|activity/.test(value)) return "announcements";
      if (/verif|lock|appeal|access/.test(value)) return "verification";
      return "dashboard";
    };
    if (tabs.length) {
      tabs.forEach(button => button.addEventListener("click", () => {
        const controller = controllers[0];
        controller.crossFade(sceneForLabel(button.textContent || button.getAttribute("aria-label")));
      }));
    }
  }

  document.addEventListener("visibilitychange", () => {
    controllers.forEach(controller => {
      if (document.hidden) controller.stop();
      else if (controller.target.getBoundingClientRect().bottom > 0 && controller.target.getBoundingClientRect().top < window.innerHeight) controller.start();
    });
  });
})();
